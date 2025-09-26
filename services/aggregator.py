"""Data aggregation service for combining processing results into structured JSON."""

import logging
import time
from typing import List, Dict, Any
from datetime import datetime

from models.schemas import (
    ProcessedDocument, 
    ProcessingStatus, 
    ExtractedData, 
    PageMetadata,
    ProcessingSummary,
    ProcessDocumentsResponse
)
from utils.tracking import ProcessingMetrics

logger = logging.getLogger(__name__)


class DataAggregator:
    """Service for aggregating processing results into structured output."""
    
    def __init__(self):
        pass
    
    def aggregate_results(
        self, 
        processed_files: List[Dict[str, Any]], 
        vision_results: List[Dict[str, Any]],
        processing_id: str,
        metrics: ProcessingMetrics,
        include_raw_responses: bool = False
    ) -> ProcessDocumentsResponse:
        """Aggregate all processing results into final response."""
        
        start_time = time.time()
        
        try:
            # Create mapping of page_id to vision results
            vision_results_map = {
                result['page_id']: result 
                for result in vision_results 
                if result.get('page_id')
            }
            
            processed_documents = []
            total_pages = 0
            
            # Process each file
            for file_result in processed_files:
                document = self._process_file_result(
                    file_result, 
                    vision_results_map, 
                    include_raw_responses
                )
                processed_documents.append(document)
                total_pages += document.page_count
            
            # Calculate summary
            summary = self._calculate_summary(metrics, processed_documents)
            
            # Determine overall success
            success = self._determine_overall_success(processed_documents)
            
            # Create final response
            response = ProcessDocumentsResponse(
                success=success,
                processing_id=processing_id,
                total_documents=len(processed_documents),
                total_pages=total_pages,
                processed_documents=processed_documents,
                summary=summary
            )
            
            processing_time = time.time() - start_time
            logger.info(f"Aggregated results in {processing_time:.2f}s for {len(processed_documents)} documents")
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to aggregate results: {e}")
            raise
    
    def _process_file_result(
        self, 
        file_result: Dict[str, Any], 
        vision_results_map: Dict[str, Dict[str, Any]],
        include_raw_responses: bool
    ) -> ProcessedDocument:
        """Process a single file result into ProcessedDocument."""
        
        file_info = file_result['file_info']
        document_type = file_result['document_type']
        pages = file_result['pages']
        file_errors = file_result['errors']
        
        # Process each page
        extracted_data = []
        document_errors = list(file_errors)  # Start with file-level errors
        successful_pages = 0
        total_processing_time = 0.0
        
        for page in pages:
            page_id = page['page_id']
            page_number = page['page_number']
            
            # Get vision result for this page
            vision_result = vision_results_map.get(page_id)
            
            if vision_result and vision_result.get('success'):
                # Successful processing
                page_metadata = PageMetadata(
                    page_number=page_number,
                    image_id=page_id,
                    processing_timestamp=datetime.utcnow(),
                    api_cost=vision_result.get('api_cost', 0.0),
                    processing_time=vision_result.get('processing_time', 0.0)
                )
                
                # Handle new schema format with documents array
                extracted_content = vision_result.get('extracted_content', {})
                
                # If the extracted content has the new schema format, process it
                if 'documents' in extracted_content and isinstance(extracted_content['documents'], list):
                    # For now, take the first document from the array
                    # In the future, this could be enhanced to handle multiple documents per page
                    if extracted_content['documents']:
                        document_data = extracted_content['documents'][0]
                        # Transform the new schema to be compatible with existing downstream processing
                        processed_content = {
                            'document_class': document_data.get('document_class', 'OTHER'),
                            'entities': document_data.get('entities', {}),
                            'tables': document_data.get('tables', []),
                            'text_content': document_data.get('text_content', ''),
                            'overall_confidence': document_data.get('overall_confidence', 0.0),
                            'document_id': document_data.get('document_id'),
                            'file_name': document_data.get('file_name', 'unknown')
                        }
                    else:
                        # Empty documents array
                        processed_content = {
                            'document_class': 'OTHER',
                            'entities': {},
                            'tables': [],
                            'text_content': '',
                            'overall_confidence': 0.0
                        }
                else:
                    # Fallback for old schema or unexpected format
                    processed_content = extracted_content
                
                raw_response = vision_result.get('raw_response') if include_raw_responses else None
                
                extracted_data.append(ExtractedData(
                    page_metadata=page_metadata,
                    extracted_content=processed_content,
                    raw_response=raw_response
                ))
                
                successful_pages += 1
                total_processing_time += vision_result.get('processing_time', 0.0)
                
            elif vision_result and not vision_result.get('success'):
                # Failed processing - add error
                error = vision_result.get('error')
                if error:
                    document_errors.append(error)
                
                total_processing_time += vision_result.get('processing_time', 0.0)
            
            else:
                # No vision result found - this shouldn't happen
                logger.warning(f"No vision result found for page {page_id}")
        
        # Determine processing status
        total_pages = len(pages)
        if successful_pages == 0:
            status = ProcessingStatus.FAILED
        elif successful_pages == total_pages and len(document_errors) == 0:
            status = ProcessingStatus.SUCCESS
        else:
            status = ProcessingStatus.PARTIAL
        
        return ProcessedDocument(
            filename=file_info.filename,
            document_type=document_type,
            page_count=total_pages,
            processing_status=status,
            extracted_data=extracted_data,
            errors=document_errors,
            processing_time=total_processing_time
        )
    
    def _calculate_summary(
        self, 
        metrics: ProcessingMetrics, 
        processed_documents: List[ProcessedDocument]
    ) -> ProcessingSummary:
        """Calculate processing summary statistics."""
        
        # Count API calls and costs from documents
        api_calls = 0
        total_cost = 0.0
        
        for doc in processed_documents:
            for extracted in doc.extracted_data:
                api_calls += 1
                total_cost += extracted.page_metadata.api_cost or 0.0
        
        # Calculate success rate
        total_pages = sum(doc.page_count for doc in processed_documents)
        successful_pages = sum(len(doc.extracted_data) for doc in processed_documents)
        
        success_rate = 0.0
        if total_pages > 0:
            success_rate = (successful_pages / total_pages) * 100.0
        
        return ProcessingSummary(
            total_processing_time=metrics.duration,
            api_calls_made=api_calls,
            estimated_cost=total_cost,
            success_rate=success_rate
        )
    
    def _determine_overall_success(self, processed_documents: List[ProcessedDocument]) -> bool:
        """Determine overall success status."""
        if not processed_documents:
            return False
        
        # Consider it successful if at least one document was processed successfully
        # or partially successfully
        for doc in processed_documents:
            if doc.processing_status in [ProcessingStatus.SUCCESS, ProcessingStatus.PARTIAL]:
                return True
        
        return False
    
    def create_error_response(
        self, 
        processing_id: str, 
        error_message: str, 
        metrics: ProcessingMetrics = None
    ) -> ProcessDocumentsResponse:
        """Create error response when processing fails completely."""
        
        if metrics is None:
            metrics = ProcessingMetrics()
            metrics.finish()
        
        summary = ProcessingSummary(
            total_processing_time=metrics.duration,
            api_calls_made=metrics.api_calls,
            estimated_cost=metrics.total_cost,
            success_rate=0.0
        )
        
        return ProcessDocumentsResponse(
            success=False,
            processing_id=processing_id,
            total_documents=0,
            total_pages=0,
            processed_documents=[],
            summary=summary
        )
