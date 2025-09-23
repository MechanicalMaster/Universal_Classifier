"""Pydantic models for request and response schemas."""

from datetime import datetime
from typing import List, Optional, Any, Dict, Union
from pydantic import BaseModel, Field
from enum import Enum


class ProcessingStatus(str, Enum):
    """Processing status enumeration."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class DocumentType(str, Enum):
    """Document type enumeration."""
    PDF = "pdf"
    IMAGE = "image"
    ZIP = "zip"


class ErrorCategory(str, Enum):
    """Error category enumeration."""
    FILE_FORMAT = "file_format"
    API_FAILURE = "api_failure"
    PARSING_ERROR = "parsing_error"
    SYSTEM_ERROR = "system_error"


class ProcessingOptions(BaseModel):
    """Processing options for document processing."""
    include_raw_responses: bool = Field(default=False, description="Include raw API responses")
    max_pages_per_document: int = Field(default=50, description="Maximum pages per document")
    vision_model: str = Field(default="gpt-4-vision-preview", description="Vision model to use")


class ProcessingError(BaseModel):
    """Processing error details."""
    page_number: Optional[int] = Field(None, description="Page number where error occurred")
    error_category: ErrorCategory = Field(..., description="Category of error")
    error_message: str = Field(..., description="Error message")
    retry_suggestion: Optional[str] = Field(None, description="Suggestion for retry")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")


class PageMetadata(BaseModel):
    """Metadata for a processed page."""
    page_number: int = Field(..., description="Page number within document")
    image_id: str = Field(..., description="Unique identifier for the image")
    processing_timestamp: datetime = Field(default_factory=datetime.utcnow, description="Processing timestamp")
    api_cost: Optional[float] = Field(None, description="Estimated API cost for this page")
    processing_time: float = Field(..., description="Processing time in seconds")


class ExtractedData(BaseModel):
    """Extracted data from a page."""
    page_metadata: PageMetadata = Field(..., description="Page metadata")
    extracted_content: Dict[str, Any] = Field(..., description="Extracted content from Vision API")
    raw_response: Optional[Dict[str, Any]] = Field(None, description="Raw API response (if requested)")


class ProcessedDocument(BaseModel):
    """Processed document result."""
    filename: str = Field(..., description="Original filename")
    document_type: DocumentType = Field(..., description="Type of document")
    page_count: int = Field(..., description="Number of pages processed")
    processing_status: ProcessingStatus = Field(..., description="Overall processing status")
    extracted_data: List[ExtractedData] = Field(default_factory=list, description="Extracted data from all pages")
    errors: List[ProcessingError] = Field(default_factory=list, description="Processing errors")
    processing_time: float = Field(..., description="Total processing time in seconds")


class ProcessingSummary(BaseModel):
    """Summary of processing results."""
    total_processing_time: float = Field(..., description="Total processing time in seconds")
    api_calls_made: int = Field(..., description="Number of API calls made")
    estimated_cost: float = Field(..., description="Estimated total cost")
    success_rate: float = Field(..., description="Success rate as percentage")


class ProcessDocumentsResponse(BaseModel):
    """Response for document processing."""
    success: bool = Field(..., description="Overall success status")
    processing_id: str = Field(..., description="Unique processing identifier")
    total_documents: int = Field(..., description="Total number of documents")
    total_pages: int = Field(..., description="Total number of pages")
    processed_documents: List[ProcessedDocument] = Field(..., description="Processed documents")
    summary: ProcessingSummary = Field(..., description="Processing summary")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Service status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")
    version: str = Field(default="1.0.0", description="Service version")
    uptime: Optional[float] = Field(None, description="Service uptime in seconds")


class StatusResponse(BaseModel):
    """Status check response for async processing."""
    processing_id: str = Field(..., description="Processing identifier")
    status: str = Field(..., description="Current processing status")
    progress: Optional[float] = Field(None, description="Progress percentage")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")
    result: Optional[ProcessDocumentsResponse] = Field(None, description="Result if completed")


class LimitsResponse(BaseModel):
    """Rate limits and usage response."""
    rate_limit_per_minute: int = Field(..., description="Rate limit per minute")
    current_usage: int = Field(..., description="Current usage count")
    remaining_requests: int = Field(..., description="Remaining requests")
    reset_time: datetime = Field(..., description="When the rate limit resets")
    max_file_size_mb: int = Field(..., description="Maximum file size in MB")
    max_total_pages: int = Field(..., description="Maximum total pages per request")


class FileInfo(BaseModel):
    """Information about an uploaded file."""
    filename: str = Field(..., description="Original filename")
    size: int = Field(..., description="File size in bytes")
    content_type: str = Field(..., description="MIME content type")
    file_id: str = Field(..., description="Unique file identifier")


class ProcessingJob(BaseModel):
    """Internal processing job model."""
    job_id: str = Field(..., description="Unique job identifier")
    files: List[FileInfo] = Field(..., description="Files to process")
    options: ProcessingOptions = Field(..., description="Processing options")
    status: str = Field(default="pending", description="Job status")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Job creation time")
    started_at: Optional[datetime] = Field(None, description="Job start time")
    completed_at: Optional[datetime] = Field(None, description="Job completion time")
    result: Optional[ProcessDocumentsResponse] = Field(None, description="Job result")
