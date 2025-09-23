# **PDF/Image Processing Service - Technical Specification**

## **Project Overview**
Build a FastAPI-based service that processes multiple file types (PDFs, images, ZIP archives) into a single structured JSON output using Vision Language Models for OCR and data extraction.

## **Core Requirements**

### **Input Processing Pipeline**
1. **File Type Detection & Routing:**
   - Accept single files or multiple files via API endpoint
   - Support formats: PDF, PNG, JPG, JPEG, ZIP
   - ZIP files: Extract all contained PDFs/images, process individually
   - Reject unsupported file types with clear error messages

2. **Image Standardization:**
   - PDF files: Convert each page to individual PNG images (300 DPI recommended)
   - Image files: Validate and normalize format (convert to PNG if needed)
   - All images should be optimized for Vision API consumption (max 4MB per image)
   - Generate unique identifiers for each image with source tracking

3. **Metadata Tracking:**
   - Track source filename, page numbers, file types
   - Generate processing timestamps for each stage
   - Maintain parent-child relationships (ZIP → PDFs → Pages)

### **Vision API Integration**
1. **API Configuration:**
   - Support OpenAI GPT-4 Vision API
   - Configurable API keys via environment variables
   - Rate limiting and retry logic (exponential backoff)
   - Cost tracking per request

2. **Processing Logic:**
   - Send each image to Vision API with structured prompt
   - Request JSON response format for consistent parsing
   - Handle API errors gracefully (timeout, rate limits, invalid responses)
   - Implement batch processing for efficiency

3. **Response Handling:**
   - Parse and validate JSON responses from Vision API
   - Handle malformed JSON responses
   - Store raw API responses for debugging
   - Track processing success/failure per image

### **Data Aggregation & Output**
1. **JSON Structure:**
   - Top-level array of documents
   - Each document contains: filename, page_count, processing_status, extracted_data
   - Preserve page order within documents
   - Include processing metadata (timestamps, API costs, error logs)

2. **Error Handling:**
   - Partial success support (return successful pages even if others fail)
   - Detailed error reporting per page/document
   - Categorize errors (file format, API failure, parsing error)
   - Include retry suggestions in error responses

## **API Specification**

### **Primary Endpoint**
```
POST /process-documents
Content-Type: multipart/form-data

Request:
- files: Multiple file uploads (required)
- options: JSON string with processing options (optional)
  - include_raw_responses: boolean (default: false)
  - max_pages_per_document: integer (default: 50)
  - vision_model: string (default: "gpt-4-vision-preview")

Response:
{
  "success": boolean,
  "processing_id": string,
  "total_documents": integer,
  "total_pages": integer,
  "processed_documents": [
    {
      "filename": string,
      "document_type": string,
      "page_count": integer,
      "processing_status": "success|partial|failed",
      "extracted_data": [...],
      "errors": [...],
      "processing_time": float
    }
  ],
  "summary": {
    "total_processing_time": float,
    "api_calls_made": integer,
    "estimated_cost": float,
    "success_rate": float
  }
}
```

### **Supporting Endpoints**
```
GET /health - Service health check
GET /status/{processing_id} - Check processing status (for async mode)
GET /limits - Current rate limits and usage
POST /process-documents-async - Background processing with webhook
```

## **Technical Architecture**

### **Framework & Dependencies**
- **FastAPI** for web framework
- **Pillow (PIL)** for image processing
- **PyPDF2 or pdf2image** for PDF conversion
- **python-multipart** for file uploads
- **httpx** for async HTTP requests to Vision APIs
- **pydantic** for data validation and JSON schemas
- **python-dotenv** for configuration management

### **Project Structure**
```
pdf-processor/
├── main.py                 # FastAPI app and routes
├── services/
│   ├── file_processor.py   # File type detection and conversion
│   ├── vision_service.py   # Vision API integration
│   └── aggregator.py       # JSON aggregation logic
├── models/
│   └── schemas.py          # Pydantic models for requests/responses
├── utils/
│   ├── file_utils.py       # File I/O helpers
│   └── tracking.py         # Metadata and progress tracking
├── config/
│   └── settings.py         # Environment configuration
├── requirements.txt
└── README.md
```

### **Environment Configuration**
```
OPENAI_API_KEY=your_openai_key
MAX_FILE_SIZE_MB=100
MAX_TOTAL_PAGES=200
UPLOAD_DIR=/tmp/uploads
LOG_LEVEL=INFO
RATE_LIMIT_PER_MINUTE=60
```

## **Error Handling Requirements**

### **File Processing Errors**
- Invalid file formats
- Corrupted PDFs
- Password-protected documents
- File size limits exceeded
- ZIP extraction failures

### **API Integration Errors**
- Vision API timeouts
- Rate limiting
- Invalid API responses
- Network connectivity issues
- Cost limit exceeded

### **System Errors**
- Memory limitations
- Disk space issues
- Processing timeouts
- Concurrent request limits

## **Performance Requirements**

### **Constraints**
- Maximum file size: 100MB per file
- Maximum pages: 200 pages total per request
- Request timeout: 10 minutes
- Concurrent processing: 5 requests maximum
- Memory limit: 2GB per processing job

### **Optimization Requirements**
- Stream processing for large files
- Cleanup temporary files immediately
- Memory usage monitoring and limits
- Graceful degradation under load

## **Deployment Specification**

### **Render.com Deployment**
- **Service Type:** Web Service
- **Runtime:** Python 3.11+
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Environment:** Production
- **Instance Type:** Standard (2GB RAM minimum)

### **Required Environment Variables**
- `OPENAI_API_KEY` (secret)
- `MAX_FILE_SIZE_MB=100`
- `LOG_LEVEL=INFO`
- `ENVIRONMENT=production`

### **Health Monitoring**
- Health check endpoint: `/health`
- Expected response time: <2 seconds
- Memory usage alerts at 80%
- Error rate monitoring and alerting

## **Testing Requirements**

### **Test Cases Needed**
- Single PDF processing (1-page, multi-page)
- Multiple PDF processing
- Image file processing (PNG, JPG)
- ZIP file with mixed content
- Error scenarios (corrupted files, API failures)
- Large file handling
- Concurrent request handling

### **Performance Testing**
- Load testing with 10 concurrent requests
- Memory usage profiling
- API cost estimation per document type
- Processing time benchmarks

## **Documentation Deliverables**
- API documentation (auto-generated by FastAPI)
- Setup and deployment guide
- Error code reference
- Cost estimation guide
- Performance tuning recommendations

This specification provides a complete blueprint for building a production-ready document processing service that can be deployed on Render with minimal configuration.