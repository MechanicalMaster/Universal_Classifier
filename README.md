# PDF/Image Processing Service

A FastAPI-based service that processes multiple file types (PDFs, images, ZIP archives) into structured JSON output using Vision Language Models for OCR and data extraction.

## Features

- **Multi-format Support**: Process PDFs, PNG, JPG, JPEG images, and ZIP archives
- **Vision AI Integration**: Uses OpenAI GPT-4 Vision API for intelligent document analysis
- **Batch Processing**: Handle multiple files and pages efficiently
- **Structured Output**: Returns consistent JSON format with extracted data
- **Error Handling**: Comprehensive error handling with partial success support
- **Rate Limiting**: Built-in API rate limiting and retry logic
- **Performance Monitoring**: Track processing metrics and costs

## Quick Start

### Prerequisites

- Python 3.11+
- OpenAI API key
- System dependencies for PDF processing

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd pdf-processor
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Install system dependencies (Ubuntu/Debian):
```bash
sudo apt-get update
sudo apt-get install -y poppler-utils libmagic1
```

4. Install system dependencies (macOS):
```bash
brew install poppler libmagic
```

5. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

### Environment Configuration

Create a `.env` file with the following variables:

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
VISION_MODEL=gpt-4-vision-preview
CONCURRENT_REQUESTS=5
REQUEST_TIMEOUT=600
MEMORY_LIMIT_GB=2
IMAGE_DPI=300
MAX_IMAGE_SIZE_MB=4
ENVIRONMENT=development
```

### Running the Service

#### Development
```bash
python main.py
```

#### Production
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

The service will be available at `http://localhost:8000`

- API Documentation: `http://localhost:8000/docs`
- Alternative Docs: `http://localhost:8000/redoc`

## API Usage

### Process Documents

**POST** `/process-documents`

Upload and process multiple files:

```bash
curl -X POST "http://localhost:8000/process-documents" \
  -F "files=@document1.pdf" \
  -F "files=@image1.png" \
  -F "files=@archive.zip" \
  -F 'options={"include_raw_responses": false, "max_pages_per_document": 50}'
```

#### Response Format

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
              "borrower_name": {"value": "John Doe", "normalized_value": "John Doe", "confidence": 0.95, "source": {...}},
              "company_name": {"value": "ABC Corp", "normalized_value": "ABC Corp", "confidence": 0.90, "source": {...}},
              "pan_number": {"value": "ABCDE1234F", "normalized_value": "ABCDE1234F", "confidence": 0.98, "source": {...}},
              "financials": [
                {
                  "year": "2023",
                  "turnover": {"value": "₹1,00,000", "normalized_value": 100000, "confidence": 0.92, "source": {...}},
                  "net_profit": {"value": "₹15,000", "normalized_value": 15000, "confidence": 0.88, "source": {...}}
                }
              ]
            },
            "tables": [
              {
                "title": "Financial Summary",
                "headers": ["Year", "Revenue", "Profit"],
                "rows": [["2023", "100000", "15000"]],
                "row_confidences": [0.92]
              }
            ],
            "text_content": "Extracted text from the document...",
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

### Other Endpoints

- **GET** `/health` - Service health check
- **GET** `/limits` - Current rate limits and usage
- **GET** `/status/{processing_id}` - Check processing status (future async support)
- **POST** `/process-documents-async` - Background processing (future implementation)

## Supported File Types

| Format | Extension | Notes |
|--------|-----------|-------|
| PDF | `.pdf` | Converts each page to image |
| PNG | `.png` | Direct processing |
| JPEG | `.jpg`, `.jpeg` | Direct processing |
| ZIP | `.zip` | Extracts and processes contained files |

## Processing Limits

- **File Size**: 100MB per file (configurable)
- **Total Pages**: 200 pages per request (configurable)
- **Concurrent Requests**: 5 simultaneous requests
- **Request Timeout**: 10 minutes
- **Memory Limit**: 2GB per processing job

## Error Handling

The service provides comprehensive error handling:

- **File Format Errors**: Unsupported formats, corrupted files
- **API Errors**: Vision API timeouts, rate limits, invalid responses
- **System Errors**: Memory limits, disk space, processing timeouts
- **Partial Success**: Returns successful pages even if others fail

## Deployment

### Render.com Deployment

1. **Service Configuration**:
   - Service Type: Web Service
   - Runtime: Python 3.11+
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

2. **Environment Variables**:
   Set the required environment variables in Render dashboard.

3. **Resource Requirements**:
   - Instance Type: Standard (2GB RAM minimum)
   - Disk Space: 10GB+ for temporary file processing

### Docker Deployment

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    poppler-utils \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Development

### Project Structure

```
pdf-processor/
├── main.py                 # FastAPI app and routes
├── services/
│   ├── file_processor.py   # File type detection and conversion
│   ├── vision_service.py   # Vision API integration
│   └── aggregator.py       # JSON aggregation logic
├── models/
│   └── schemas.py          # Pydantic models
├── utils/
│   ├── file_utils.py       # File I/O helpers
│   └── tracking.py         # Metadata and progress tracking
├── config/
│   └── settings.py         # Environment configuration
├── requirements.txt
└── README.md
```

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest tests/
```

### Code Quality

```bash
# Install development tools
pip install black isort flake8 mypy

# Format code
black .
isort .

# Check code quality
flake8 .
mypy .
```

## Cost Estimation

Vision API costs (approximate, as of 2024):

- **GPT-4 Vision Preview**: $0.01 per image
- **GPT-4o**: $0.0075 per image  
- **GPT-4o Mini**: $0.00025 per image

Example cost for a 10-page PDF using GPT-4 Vision: ~$0.10

## Performance Tuning

### Optimization Tips

1. **Image Quality**: Lower DPI (150-200) for faster processing
2. **Batch Size**: Process 5-10 files simultaneously for optimal throughput
3. **Memory Management**: Monitor memory usage with large files
4. **API Model**: Use GPT-4o Mini for cost-effective processing

### Monitoring

The service provides built-in metrics:
- Processing times per document/page
- API call counts and costs
- Success/failure rates
- Memory and resource usage

## Troubleshooting

### Common Issues

1. **"PDF conversion failed"**
   - Install poppler-utils: `sudo apt-get install poppler-utils`
   - Check if PDF is password-protected

2. **"Vision API timeout"**
   - Reduce image DPI in settings
   - Check network connectivity
   - Verify API key is valid

3. **"File too large"**
   - Increase MAX_FILE_SIZE_MB in environment
   - Compress images before processing

4. **Memory issues**
   - Reduce concurrent requests
   - Process fewer pages per request
   - Increase server memory allocation

### Logs

Check application logs for detailed error information:
```bash
# View logs in development
python main.py

# View logs in production (systemd)
journalctl -u pdf-processor -f

# View logs in Docker
docker logs container_name -f
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure code quality checks pass
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
- Check the troubleshooting section
- Review API documentation at `/docs`
- Open an issue on GitHub
- Check logs for detailed error information
