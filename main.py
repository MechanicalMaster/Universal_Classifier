"""FastAPI application for PDF/Image processing service."""

import os
import json
import logging
import asyncio
from datetime import datetime
from typing import List, Optional
import uuid
import time

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from models.schemas import (
    ProcessDocumentsResponse,
    HealthResponse,
    StatusResponse,
    LimitsResponse,
    ProcessingOptions,
    FileInfo,
    ProcessingJob
)
from services.file_processor import FileProcessor
from services.vision_service import VisionService
from services.aggregator import DataAggregator
from utils.file_utils import FileUtils
from utils.tracking import progress_tracker, rate_limit_tracker
from config.settings import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="PDF/Image Processing Service",
    description="A service for processing PDFs, images, and ZIP archives using Vision Language Models",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables for tracking
processing_jobs: dict = {}
app_start_time = time.time()

# Ensure upload directory exists
FileUtils.ensure_upload_directory()


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    logger.info("Starting PDF/Image Processing Service")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Upload directory: {settings.upload_dir}")
    logger.info(f"Max file size: {settings.max_file_size_mb}MB")
    logger.info(f"Max pages per request: {settings.max_total_pages}")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    logger.info("Shutting down PDF/Image Processing Service")
    # Clean up any remaining temporary files
    # This would be handled by individual processors


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    uptime = time.time() - app_start_time
    
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version="1.0.0",
        uptime=uptime
    )


@app.get("/limits", response_model=LimitsResponse)
async def get_limits():
    """Get current rate limits and usage information."""
    usage_info = rate_limit_tracker.get_usage_info()
    
    return LimitsResponse(
        rate_limit_per_minute=usage_info['rate_limit'],
        current_usage=usage_info['current_usage'],
        remaining_requests=usage_info['remaining'],
        reset_time=usage_info['reset_time'] or datetime.utcnow(),
        max_file_size_mb=settings.max_file_size_mb,
        max_total_pages=settings.max_total_pages
    )


@app.post("/process-documents", response_model=ProcessDocumentsResponse)
async def process_documents(
    files: List[UploadFile] = File(...),
    options: Optional[str] = Form(None)
):
    """Process multiple documents (PDFs, images, ZIP archives)."""
    
    processing_id = str(uuid.uuid4())
    logger.info(f"Starting document processing job: {processing_id}")
    
    # Start tracking
    metrics = progress_tracker.start_job(processing_id)
    
    # Initialize services
    file_processor = FileProcessor()
    vision_service = VisionService()
    aggregator = DataAggregator()
    
    temp_dir = None
    
    try:
        # Parse options
        processing_options = ProcessingOptions()
        if options:
            try:
                options_dict = json.loads(options)
                processing_options = ProcessingOptions(**options_dict)
            except json.JSONDecodeError as e:
                raise HTTPException(status_code=400, detail=f"Invalid options JSON: {e}")
        
        # Validate request
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
        
        if len(files) > 10:  # Reasonable limit
            raise HTTPException(status_code=400, detail="Too many files (max 10)")
        
        # Create temporary directory
        temp_dir = FileUtils.create_temp_directory()
        logger.info(f"Created temporary directory: {temp_dir}")
        
        # Save uploaded files and create FileInfo objects
        file_infos = []
        total_size = 0
        
        for upload_file in files:
            # Read file content
            content = await upload_file.read()
            total_size += len(content)
            
            # Check total size
            max_total_size = settings.max_file_size_mb * 1024 * 1024 * len(files)
            if total_size > max_total_size:
                raise HTTPException(
                    status_code=413, 
                    detail=f"Total files size too large (max {settings.max_file_size_mb * len(files)}MB)"
                )
            
            # Save file
            file_path = FileUtils.save_uploaded_file(content, upload_file.filename, temp_dir)
            
            # Create FileInfo
            file_info = FileInfo(
                filename=upload_file.filename,
                size=len(content),
                content_type=upload_file.content_type or "application/octet-stream",
                file_id=FileUtils.generate_unique_id("file_")
            )
            file_infos.append(file_info)
        
        logger.info(f"Saved {len(file_infos)} files, total size: {total_size / (1024*1024):.2f}MB")
        
        # Process files
        logger.info("Starting file processing...")
        processed_files = await file_processor.process_files(file_infos, temp_dir)
        
        # Collect all pages for vision processing
        all_pages = []
        for file_result in processed_files:
            all_pages.extend(file_result['pages'])
        
        logger.info(f"Processing {len(all_pages)} pages through Vision API...")
        
        # Check page limit
        if len(all_pages) > settings.max_total_pages:
            raise HTTPException(
                status_code=413,
                detail=f"Too many pages ({len(all_pages)}), max allowed: {settings.max_total_pages}"
            )
        
        # Process through Vision API
        vision_results = []
        if all_pages:
            vision_results = await vision_service.process_images(all_pages)
        
        logger.info(f"Vision API processing completed, {len(vision_results)} results")
        
        # Update metrics
        for result in vision_results:
            if result.get('success'):
                metrics.add_success()
                metrics.add_api_call(result.get('api_cost', 0.0))
            else:
                error_info = {
                    'page_id': result.get('page_id'),
                    'error': str(result.get('error', 'Unknown error'))
                }
                metrics.add_failure(error_info)
        
        # Aggregate results
        logger.info("Aggregating results...")
        response = aggregator.aggregate_results(
            processed_files=processed_files,
            vision_results=vision_results,
            processing_id=processing_id,
            metrics=metrics,
            include_raw_responses=processing_options.include_raw_responses
        )
        
        logger.info(f"Processing completed successfully: {processing_id}")
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
        
    except Exception as e:
        logger.error(f"Processing failed for job {processing_id}: {e}")
        
        # Create error response
        error_response = aggregator.create_error_response(
            processing_id=processing_id,
            error_message=str(e),
            metrics=metrics
        )
        
        raise HTTPException(status_code=500, detail=error_response.dict())
        
    finally:
        # Clean up
        metrics.finish()
        progress_tracker.finish_job(processing_id)
        
        if temp_dir:
            FileUtils.cleanup_directory(temp_dir)
            logger.info(f"Cleaned up temporary directory: {temp_dir}")


@app.get("/status/{processing_id}", response_model=StatusResponse)
async def get_processing_status(processing_id: str):
    """Get processing status for async operations (placeholder for future async implementation)."""
    
    # For now, this is a placeholder since we're doing synchronous processing
    # In a future version, this could track async jobs
    
    job = processing_jobs.get(processing_id)
    if not job:
        raise HTTPException(status_code=404, detail="Processing job not found")
    
    return StatusResponse(
        processing_id=processing_id,
        status=job.get('status', 'unknown'),
        progress=job.get('progress'),
        estimated_completion=job.get('estimated_completion'),
        result=job.get('result')
    )


@app.post("/process-documents-async")
async def process_documents_async(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    options: Optional[str] = Form(None)
):
    """Process documents in the background (placeholder for future async implementation)."""
    
    # For now, this is a placeholder
    # In a production system, you would:
    # 1. Store files temporarily
    # 2. Queue the job for background processing
    # 3. Return job ID immediately
    # 4. Process in background and store results
    # 5. Provide webhook notifications when complete
    
    processing_id = str(uuid.uuid4())
    
    # Store job info
    processing_jobs[processing_id] = {
        'status': 'queued',
        'created_at': datetime.utcnow(),
        'files_count': len(files)
    }
    
    return {
        "processing_id": processing_id,
        "status": "queued",
        "message": "Job queued for background processing. Use /status/{processing_id} to check progress."
    }


@app.exception_handler(413)
async def payload_too_large_handler(request, exc):
    """Handle payload too large errors."""
    return JSONResponse(
        status_code=413,
        content={
            "detail": f"File too large. Maximum size allowed: {settings.max_file_size_mb}MB",
            "error_code": "PAYLOAD_TOO_LARGE"
        }
    )


@app.exception_handler(500)
async def internal_server_error_handler(request, exc):
    """Handle internal server errors."""
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error occurred during processing",
            "error_code": "INTERNAL_SERVER_ERROR"
        }
    )


if __name__ == "__main__":
    # For development
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        reload=settings.environment == "development",
        log_level=settings.log_level.lower()
    )
