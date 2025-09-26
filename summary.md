# PDF/Image Processing Service - Codebase Summary

## Overview

This is a comprehensive FastAPI-based service designed for processing multiple file types (PDFs, images, ZIP archives) and extracting structured data using OpenAI's GPT-4 Vision API. The service provides intelligent document analysis, OCR capabilities, and structured JSON output for various document types.

## Architecture & Structure

### Core Components

#### 1. **Main Application** (`main.py`)
- FastAPI application with comprehensive routing
- Health checks and monitoring endpoints
- File upload handling with validation
- Background processing infrastructure
- Error handling and middleware

#### 2. **Services Layer**
- **VisionService** (`services/vision_service.py`): OpenAI Vision API integration
- **FileProcessor** (`services/file_processor.py`): Multi-format file processing
- **DataAggregator** (`services/aggregator.py`): Result aggregation and formatting

#### 3. **Data Models** (`models/schemas.py`)
- Pydantic models for request/response validation
- Comprehensive type definitions for all data structures
- Document classification enums for credit underwriting

#### 4. **Utilities** (`utils/`)
- **FileUtils**: File handling, validation, and optimization
- **Tracking**: Performance monitoring, rate limiting, and metadata tracking

#### 5. **Configuration** (`config/settings.py`)
- Environment-based configuration management
- Comprehensive settings for all service aspects

## Key Features

### 1. **Multi-Format Support**
- **PDF Documents**: Automatic page extraction and image conversion
- **Images**: Direct processing (PNG, JPG, JPEG)
- **ZIP Archives**: Extraction and processing of contained files
- **Batch Processing**: Handle multiple files simultaneously

### 2. **Vision AI Integration**
- OpenAI GPT-4 Vision API integration
- Intelligent document analysis and OCR
- Configurable vision models (GPT-4o, GPT-4o-mini, etc.)
- Rate limiting and retry logic with exponential backoff

### 3. **Advanced Processing**
- Image optimization for API consumption
- Concurrent processing with controlled parallelism
- Memory and resource management
- Progress tracking and metrics collection

### 4. **Document Classification**
- Specialized for credit underwriting documents
- Pre-defined document classes (PAN, AADHAAR, GST, Financial Statements, etc.)
- Entity extraction and normalization
- Table and structured data recognition

## API Endpoints

### Core Processing Endpoint

#### `POST /process-documents`
**Purpose**: Process multiple documents with Vision AI analysis

**Parameters**:
- `files`: List of files to process (PDF, images, ZIP)
- `options`: JSON string with processing options

**Request Example**:
```bash
curl -X POST "http://localhost:8000/process-documents" \
  -F "files=@document1.pdf" \
  -F "files=@image1.png" \
  -F "files=@archive.zip" \
  -F 'options={"include_raw_responses": false, "max_pages_per_document": 50}'
```

**Processing Options**:
- `include_raw_responses`: Include full API responses (default: false)
- `max_pages_per_document`: Page limit per document (default: 50)
- `vision_model`: Model to use (default: gpt-4o)

### Utility Endpoints

#### `GET /health`
**Purpose**: Service health check
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "version": "1.0.0",
  "uptime": 3600.5
}
```

#### `GET /limits`
**Purpose**: Current rate limits and usage
```json
{
  "rate_limit_per_minute": 60,
  "current_usage": 15,
  "remaining_requests": 45,
  "reset_time": "2024-01-01T12:05:00Z",
  "max_file_size_mb": 100,
  "max_total_pages": 200
}
```

#### `GET /status/{processing_id}`
**Purpose**: Check processing status (for future async support)

#### `POST /process-documents-async`
**Purpose**: Background processing endpoint (placeholder)

## Response Format

### Successful Response Structure
```json
{
  "success": true,
  "processing_id": "uuid-string",
  "total_documents": 3,
  "total_pages": 15,
  "processed_documents": [
    {
      "filename": "document1.pdf",
      "document_type": "pdf",
      "page_count": 5,
      "processing_status": "success",
      "extracted_data": [
        {
          "page_metadata": {
            "page_number": 1,
            "image_id": "page_1_abc123",
            "processing_timestamp": "2024-01-01T12:00:00Z",
            "api_cost": 0.01,
            "processing_time": 2.5
          },
          "extracted_content": {
            "document_class": "FINANCIAL_STATEMENT",
            "entities": {
              "borrower_name": {
                "value": "John Doe",
                "normalized_value": "John Doe",
                "confidence": 0.95,
                "source": {...}
              }
            },
            "tables": [...],
            "text_content": "Extracted text...",
            "overall_confidence": 0.91
          }
        }
      ],
      "errors": [],
      "processing_time": 12.5
    }
  ],
  "summary": {
    "total_processing_time": 45.2,
    "api_calls_made": 15,
    "estimated_cost": 0.15,
    "success_rate": 95.5
  }
}
```

## Document Classes & Entity Types

### Supported Document Classes
- `PAN_FIRM` - PAN card for firms
- `PAN_INDIVIDUAL` - PAN card for individuals
- `AADHAAR_INDIVIDUAL` - Aadhaar card
- `UDYAM_REGISTRATION` - Udyam registration certificate
- `PARTNERSHIP_DEED` - Partnership deed
- `GST_CERTIFICATE` - GST registration certificate
- `BANK_STATEMENT` - Bank statements
- `FINANCIAL_STATEMENT` - Financial statements
- `ITR_INDIVIDUAL` - Income Tax Return (individual)
- `ITR_FIRM` - Income Tax Return (firm)

### Extracted Entities
- **Personal Information**: Names, addresses, phone numbers
- **Financial Data**: Turnover, profit, financial metrics
- **Identification**: PAN numbers, Aadhaar numbers, GST numbers
- **Business Information**: Company names, registration details
- **Tables**: Structured data extraction from tables

## Configuration & Environment

### Required Environment Variables
```env
# Required
OPENAI_API_KEY=your_openai_api_key_here

# Optional (with defaults)
MAX_FILE_SIZE_MB=100
MAX_TOTAL_PAGES=200
MAX_PAGES_PER_DOCUMENT=50
UPLOAD_DIR=/tmp/uploads
LOG_LEVEL=INFO
RATE_LIMIT_PER_MINUTE=60
VISION_MODEL=gpt-4o
CONCURRENT_REQUESTS=5
REQUEST_TIMEOUT=600
MEMORY_LIMIT_GB=2
IMAGE_DPI=300
MAX_IMAGE_SIZE_MB=4
ENVIRONMENT=development
```

### Processing Limits
- **File Size**: Up to 100MB per file (configurable)
- **Total Pages**: Up to 200 pages per request
- **Concurrent Requests**: Up to 5 simultaneous requests
- **Request Timeout**: 10 minutes
- **Memory Limit**: 2GB per processing job

## Performance & Cost Optimization

### Vision API Models
- **GPT-4o**: $0.00765 per image (recommended)
- **GPT-4o-mini**: $0.00025 per image (cost-effective)
- **GPT-4 Vision Preview**: $0.01 per image (legacy)

### Performance Features
- **Concurrent Processing**: Limited to 3 concurrent Vision API calls
- **Rate Limiting**: Built-in rate limiting with capacity management
- **Image Optimization**: Automatic image compression for API efficiency
- **Retry Logic**: Exponential backoff with configurable retries
- **Memory Management**: Controlled resource usage

### Monitoring & Metrics
- Processing times per document/page
- API call counts and costs
- Success/failure rates
- Resource usage tracking

## Error Handling & Resilience

### Error Categories
- `FILE_FORMAT` - Unsupported formats, corrupted files
- `API_FAILURE` - Vision API errors, timeouts, rate limits
- `PARSING_ERROR` - Data parsing and extraction errors
- `SYSTEM_ERROR` - Memory limits, system failures

### Resilience Features
- **Partial Success**: Returns successful pages even if others fail
- **Retry Logic**: Automatic retries with exponential backoff
- **Rate Limit Handling**: Intelligent rate limit management
- **Memory Protection**: Built-in memory monitoring
- **Graceful Degradation**: Continues processing despite individual failures

## Deployment Options

### Development
```bash
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Production (Render.com)
```bash
# Build Command: pip install -r requirements.txt
# Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
```

### Docker Deployment
```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y poppler-utils libmagic1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Dependencies

### Core Dependencies
- **FastAPI**: Web framework
- **OpenAI**: Vision API integration
- **Pillow**: Image processing
- **pdf2image/PyPDF2**: PDF processing
- **httpx**: Async HTTP client
- **pydantic**: Data validation
- **python-multipart**: File upload handling

### System Dependencies
- **poppler-utils**: PDF to image conversion
- **libmagic**: File type detection

## Development Workflow

### Local Development
1. Install dependencies: `pip install -r requirements.txt`
2. Install system dependencies
3. Set up environment variables
4. Run: `python main.py`

### Testing
- Unit tests for individual components
- Integration tests for API endpoints
- Load testing for performance validation

### Code Quality
- Type hints throughout codebase
- Comprehensive error handling
- Logging and monitoring
- Performance optimization

## Security Considerations

### API Security
- OpenAI API key protection
- File upload validation and sanitization
- Rate limiting to prevent abuse
- Input validation and sanitization

### Data Protection
- Temporary file cleanup
- No persistent storage of uploaded files
- Memory-safe processing
- Secure file handling

## Future Enhancements

### Planned Features
- Async processing with webhook notifications
- Database integration for job persistence
- Advanced document classification
- Custom model training capabilities
- Multi-language support
- Enhanced table extraction
- Real-time progress streaming

### Scalability Improvements
- Horizontal scaling support
- Queue-based processing
- Caching layer implementation
- Database optimization
- Load balancing

## Troubleshooting

### Common Issues
1. **PDF Conversion Failed**: Install poppler-utils
2. **Vision API Timeout**: Reduce image DPI or check network
3. **File Too Large**: Increase MAX_FILE_SIZE_MB or compress files
4. **Memory Issues**: Reduce concurrent requests or increase server memory
5. **Rate Limiting**: Check API key limits and usage

### Debug Information
- Comprehensive logging at configurable levels
- Detailed error messages with suggestions
- Performance metrics and timing information
- API call tracking and cost estimation

## Conclusion

This service provides a robust, scalable solution for document processing using state-of-the-art Vision AI technology. It combines intelligent document analysis with enterprise-grade reliability, making it suitable for production environments requiring high accuracy and performance in document processing workflows.

The architecture is designed for extensibility, with clear separation of concerns and comprehensive error handling, making it easy to maintain and enhance with new features and capabilities.
