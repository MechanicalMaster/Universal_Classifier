"""File processing service for handling PDFs, images, and ZIP archives."""

import os
import logging
from typing import List, Dict, Any, Tuple
from PIL import Image
import pdf2image
from PyPDF2 import PdfReader
import tempfile

from models.schemas import DocumentType, ProcessingError, ErrorCategory, FileInfo
from utils.file_utils import FileUtils
from utils.tracking import metadata_tracker
from config.settings import settings

logger = logging.getLogger(__name__)


class FileProcessor:
    """Service for processing different file types."""
    
    def __init__(self):
        self.temp_dirs: List[str] = []
    
    async def process_files(self, files: List[FileInfo], temp_dir: str) -> List[Dict[str, Any]]:
        """Process multiple files and return structured data."""
        processed_files = []
        
        for file_info in files:
            try:
                file_path = os.path.join(temp_dir, file_info.filename)
                
                # Validate file
                if not FileUtils.is_supported_file(file_path):
                    error = ProcessingError(
                        error_category=ErrorCategory.FILE_FORMAT,
                        error_message=f"Unsupported file type: {file_info.filename}",
                        retry_suggestion="Please use supported formats: PDF, PNG, JPG, JPEG, ZIP"
                    )
                    processed_files.append({
                        'file_info': file_info,
                        'document_type': None,
                        'pages': [],
                        'errors': [error]
                    })
                    continue
                
                if not FileUtils.validate_file_size(file_path):
                    error = ProcessingError(
                        error_category=ErrorCategory.FILE_FORMAT,
                        error_message=f"File too large: {file_info.filename}",
                        retry_suggestion=f"Please reduce file size below {settings.max_file_size_mb}MB"
                    )
                    processed_files.append({
                        'file_info': file_info,
                        'document_type': None,
                        'pages': [],
                        'errors': [error]
                    })
                    continue
                
                # Process based on file type
                result = await self._process_single_file(file_path, file_info, temp_dir)
                processed_files.append(result)
                
            except Exception as e:
                logger.error(f"Failed to process file {file_info.filename}: {e}")
                error = ProcessingError(
                    error_category=ErrorCategory.SYSTEM_ERROR,
                    error_message=f"Processing failed: {str(e)}",
                    retry_suggestion="Please try again or contact support"
                )
                processed_files.append({
                    'file_info': file_info,
                    'document_type': None,
                    'pages': [],
                    'errors': [error]
                })
        
        return processed_files
    
    async def _process_single_file(self, file_path: str, file_info: FileInfo, temp_dir: str) -> Dict[str, Any]:
        """Process a single file based on its type."""
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == '.pdf':
            return await self._process_pdf(file_path, file_info, temp_dir)
        elif ext in {'.png', '.jpg', '.jpeg'}:
            return await self._process_image(file_path, file_info, temp_dir)
        elif ext == '.zip':
            return await self._process_zip(file_path, file_info, temp_dir)
        else:
            error = ProcessingError(
                error_category=ErrorCategory.FILE_FORMAT,
                error_message=f"Unsupported file extension: {ext}",
                retry_suggestion="Please use supported formats: PDF, PNG, JPG, JPEG, ZIP"
            )
            return {
                'file_info': file_info,
                'document_type': None,
                'pages': [],
                'errors': [error]
            }
    
    async def _process_pdf(self, pdf_path: str, file_info: FileInfo, temp_dir: str) -> Dict[str, Any]:
        """Process PDF file by converting pages to images."""
        pages = []
        errors = []
        
        try:
            # First, try to get page count
            with open(pdf_path, 'rb') as file:
                pdf_reader = PdfReader(file)
                total_pages = len(pdf_reader.pages)
            
            if total_pages > settings.max_pages_per_document:
                error = ProcessingError(
                    error_category=ErrorCategory.FILE_FORMAT,
                    error_message=f"PDF has too many pages: {total_pages}",
                    retry_suggestion=f"Please split PDF to have max {settings.max_pages_per_document} pages"
                )
                return {
                    'file_info': file_info,
                    'document_type': DocumentType.PDF,
                    'pages': [],
                    'errors': [error]
                }
            
            # Convert PDF pages to images
            try:
                images = pdf2image.convert_from_path(
                    pdf_path,
                    dpi=settings.image_dpi,
                    fmt='PNG'
                )
                
                for page_num, image in enumerate(images, 1):
                    try:
                        # Save page as image
                        page_id = FileUtils.generate_unique_id(f"page_{page_num}_")
                        image_path = os.path.join(temp_dir, f"{page_id}.png")
                        
                        # Save and optimize image
                        image.save(image_path, 'PNG')
                        
                        # Optimize for API
                        optimized_path = os.path.join(temp_dir, f"{page_id}_opt.png")
                        if FileUtils.optimize_image_for_api(image_path, optimized_path):
                            # Add metadata
                            metadata_tracker.add_page_metadata(
                                page_id=page_id,
                                file_id=file_info.file_id,
                                page_number=page_num,
                                metadata={
                                    'source_file': file_info.filename,
                                    'image_path': optimized_path,
                                    'original_format': 'pdf'
                                }
                            )
                            
                            pages.append({
                                'page_id': page_id,
                                'page_number': page_num,
                                'image_path': optimized_path
                            })
                        else:
                            error = ProcessingError(
                                page_number=page_num,
                                error_category=ErrorCategory.SYSTEM_ERROR,
                                error_message=f"Failed to optimize page {page_num}",
                                retry_suggestion="Try reducing PDF quality or size"
                            )
                            errors.append(error)
                    
                    except Exception as e:
                        logger.error(f"Failed to process PDF page {page_num}: {e}")
                        error = ProcessingError(
                            page_number=page_num,
                            error_category=ErrorCategory.SYSTEM_ERROR,
                            error_message=f"Page processing failed: {str(e)}",
                            retry_suggestion="Try again or check PDF integrity"
                        )
                        errors.append(error)
            
            except Exception as e:
                logger.error(f"Failed to convert PDF to images: {e}")
                error = ProcessingError(
                    error_category=ErrorCategory.SYSTEM_ERROR,
                    error_message=f"PDF conversion failed: {str(e)}",
                    retry_suggestion="Check if PDF is corrupted or password-protected"
                )
                errors.append(error)
        
        except Exception as e:
            logger.error(f"Failed to read PDF {pdf_path}: {e}")
            error = ProcessingError(
                error_category=ErrorCategory.FILE_FORMAT,
                error_message=f"Cannot read PDF: {str(e)}",
                retry_suggestion="Check if PDF is corrupted or password-protected"
            )
            errors.append(error)
        
        return {
            'file_info': file_info,
            'document_type': DocumentType.PDF,
            'pages': pages,
            'errors': errors
        }
    
    async def _process_image(self, image_path: str, file_info: FileInfo, temp_dir: str) -> Dict[str, Any]:
        """Process image file."""
        pages = []
        errors = []
        
        try:
            # Validate and optimize image
            page_id = FileUtils.generate_unique_id(f"img_")
            optimized_path = os.path.join(temp_dir, f"{page_id}_opt.png")
            
            if FileUtils.optimize_image_for_api(image_path, optimized_path):
                # Add metadata
                metadata_tracker.add_page_metadata(
                    page_id=page_id,
                    file_id=file_info.file_id,
                    page_number=1,
                    metadata={
                        'source_file': file_info.filename,
                        'image_path': optimized_path,
                        'original_format': 'image'
                    }
                )
                
                pages.append({
                    'page_id': page_id,
                    'page_number': 1,
                    'image_path': optimized_path
                })
            else:
                error = ProcessingError(
                    error_category=ErrorCategory.SYSTEM_ERROR,
                    error_message="Failed to optimize image",
                    retry_suggestion="Try reducing image size or changing format"
                )
                errors.append(error)
        
        except Exception as e:
            logger.error(f"Failed to process image {image_path}: {e}")
            error = ProcessingError(
                error_category=ErrorCategory.SYSTEM_ERROR,
                error_message=f"Image processing failed: {str(e)}",
                retry_suggestion="Check if image file is corrupted"
            )
            errors.append(error)
        
        return {
            'file_info': file_info,
            'document_type': DocumentType.IMAGE,
            'pages': pages,
            'errors': errors
        }
    
    async def _process_zip(self, zip_path: str, file_info: FileInfo, temp_dir: str) -> Dict[str, Any]:
        """Process ZIP archive by extracting and processing contained files."""
        pages = []
        errors = []
        
        try:
            # Create subdirectory for extracted files
            extract_dir = os.path.join(temp_dir, f"extracted_{file_info.file_id}")
            os.makedirs(extract_dir, exist_ok=True)
            
            # Extract ZIP contents
            extracted_files = FileUtils.extract_zip_file(zip_path, extract_dir)
            
            if not extracted_files:
                error = ProcessingError(
                    error_category=ErrorCategory.FILE_FORMAT,
                    error_message="No supported files found in ZIP archive",
                    retry_suggestion="Ensure ZIP contains PDF, PNG, JPG, or JPEG files"
                )
                errors.append(error)
                return {
                    'file_info': file_info,
                    'document_type': DocumentType.ZIP,
                    'pages': pages,
                    'errors': errors
                }
            
            # Process each extracted file
            page_counter = 1
            for extracted_file in extracted_files:
                try:
                    # Create temporary FileInfo for extracted file
                    extracted_info = FileInfo(
                        filename=os.path.basename(extracted_file),
                        size=os.path.getsize(extracted_file),
                        content_type=FileUtils.get_file_type(extracted_file),
                        file_id=FileUtils.generate_unique_id("extracted_")
                    )
                    
                    # Process extracted file
                    result = await self._process_single_file(extracted_file, extracted_info, extract_dir)
                    
                    # Add pages with adjusted page numbers
                    for page in result['pages']:
                        page['page_number'] = page_counter
                        page_counter += 1
                        pages.append(page)
                    
                    # Collect errors
                    errors.extend(result['errors'])
                
                except Exception as e:
                    logger.error(f"Failed to process extracted file {extracted_file}: {e}")
                    error = ProcessingError(
                        error_category=ErrorCategory.SYSTEM_ERROR,
                        error_message=f"Failed to process {os.path.basename(extracted_file)}: {str(e)}",
                        retry_suggestion="Check if extracted file is corrupted"
                    )
                    errors.append(error)
        
        except Exception as e:
            logger.error(f"Failed to process ZIP file {zip_path}: {e}")
            error = ProcessingError(
                error_category=ErrorCategory.SYSTEM_ERROR,
                error_message=f"ZIP processing failed: {str(e)}",
                retry_suggestion="Check if ZIP file is corrupted"
            )
            errors.append(error)
        
        return {
            'file_info': file_info,
            'document_type': DocumentType.ZIP,
            'pages': pages,
            'errors': errors
        }
    
    def cleanup(self) -> None:
        """Clean up temporary directories."""
        for temp_dir in self.temp_dirs:
            FileUtils.cleanup_directory(temp_dir)
