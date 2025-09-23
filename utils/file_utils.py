"""File utility functions for handling file operations."""

import os
import uuid
import magic
import shutil
import zipfile
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from PIL import Image
import tempfile
import logging

from config.settings import settings

logger = logging.getLogger(__name__)


class FileUtils:
    """Utility class for file operations."""
    
    SUPPORTED_IMAGE_FORMATS = {'.png', '.jpg', '.jpeg'}
    SUPPORTED_DOCUMENT_FORMATS = {'.pdf'}
    SUPPORTED_ARCHIVE_FORMATS = {'.zip'}
    
    @classmethod
    def get_file_type(cls, file_path: str) -> str:
        """Detect file type using python-magic."""
        try:
            mime_type = magic.from_file(file_path, mime=True)
            return mime_type
        except Exception as e:
            logger.warning(f"Could not detect MIME type for {file_path}: {e}")
            # Fallback to extension-based detection
            ext = Path(file_path).suffix.lower()
            if ext in cls.SUPPORTED_IMAGE_FORMATS:
                return f"image/{ext[1:]}"
            elif ext == '.pdf':
                return "application/pdf"
            elif ext == '.zip':
                return "application/zip"
            return "application/octet-stream"
    
    @classmethod
    def is_supported_file(cls, file_path: str) -> bool:
        """Check if file type is supported."""
        ext = Path(file_path).suffix.lower()
        return ext in (cls.SUPPORTED_IMAGE_FORMATS | 
                      cls.SUPPORTED_DOCUMENT_FORMATS | 
                      cls.SUPPORTED_ARCHIVE_FORMATS)
    
    @classmethod
    def validate_file_size(cls, file_path: str) -> bool:
        """Validate file size against limits."""
        file_size = os.path.getsize(file_path)
        max_size = settings.max_file_size_mb * 1024 * 1024
        return file_size <= max_size
    
    @classmethod
    def create_temp_directory(cls) -> str:
        """Create a temporary directory for processing."""
        temp_dir = os.path.join(settings.upload_dir, str(uuid.uuid4()))
        os.makedirs(temp_dir, exist_ok=True)
        return temp_dir
    
    @classmethod
    def cleanup_directory(cls, directory: str) -> None:
        """Clean up temporary directory."""
        try:
            if os.path.exists(directory):
                shutil.rmtree(directory)
                logger.info(f"Cleaned up directory: {directory}")
        except Exception as e:
            logger.error(f"Failed to cleanup directory {directory}: {e}")
    
    @classmethod
    def extract_zip_file(cls, zip_path: str, extract_to: str) -> List[str]:
        """Extract ZIP file and return list of extracted files."""
        extracted_files = []
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Get list of files in the ZIP
                file_list = zip_ref.namelist()
                
                for file_name in file_list:
                    # Skip directories
                    if file_name.endswith('/'):
                        continue
                    
                    # Skip macOS system files and corrupted files
                    if (file_name.startswith('__MACOSX/') or 
                        file_name.endswith('.DS_Store') or
                        file_name.startswith('._')):
                        logger.warning(f"Skipping system/corrupted file in ZIP: {file_name}")
                        continue
                    
                    # Extract file
                    zip_ref.extract(file_name, extract_to)
                    extracted_path = os.path.join(extract_to, file_name)
                    
                    # Check if extracted file is supported
                    if cls.is_supported_file(extracted_path):
                        extracted_files.append(extracted_path)
                    else:
                        logger.warning(f"Unsupported file in ZIP: {file_name}")
                        os.remove(extracted_path)
                
                logger.info(f"Extracted {len(extracted_files)} supported files from ZIP")
                return extracted_files
                
        except zipfile.BadZipFile:
            logger.error(f"Invalid ZIP file: {zip_path}")
            raise ValueError("Invalid ZIP file")
        except Exception as e:
            logger.error(f"Failed to extract ZIP file {zip_path}: {e}")
            raise
    
    @classmethod
    def optimize_image_for_api(cls, image_path: str, output_path: str) -> bool:
        """Optimize image for Vision API consumption."""
        try:
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Calculate size to stay under API limits
                max_size = settings.max_image_size_mb * 1024 * 1024
                
                # Save with optimization
                quality = 95
                while True:
                    img.save(output_path, 'PNG', optimize=True, quality=quality)
                    
                    if os.path.getsize(output_path) <= max_size or quality <= 20:
                        break
                    
                    quality -= 10
                
                logger.info(f"Optimized image: {image_path} -> {output_path}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to optimize image {image_path}: {e}")
            return False
    
    @classmethod
    def generate_unique_id(cls, prefix: str = "") -> str:
        """Generate a unique identifier."""
        return f"{prefix}{uuid.uuid4().hex[:8]}"
    
    @classmethod
    def save_uploaded_file(cls, file_data: bytes, filename: str, temp_dir: str) -> str:
        """Save uploaded file data to temporary directory."""
        file_path = os.path.join(temp_dir, filename)
        
        with open(file_path, 'wb') as f:
            f.write(file_data)
        
        logger.info(f"Saved uploaded file: {file_path}")
        return file_path
    
    @classmethod
    def get_file_info(cls, file_path: str) -> Dict[str, Any]:
        """Get file information."""
        stat = os.stat(file_path)
        return {
            'filename': os.path.basename(file_path),
            'size': stat.st_size,
            'mime_type': cls.get_file_type(file_path),
            'modified_time': stat.st_mtime
        }
    
    @classmethod
    def ensure_upload_directory(cls) -> None:
        """Ensure upload directory exists."""
        os.makedirs(settings.upload_dir, exist_ok=True)
