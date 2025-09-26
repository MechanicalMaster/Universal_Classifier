"""Vision API service for processing images with OpenAI GPT-4 Vision."""

import asyncio
import base64
import json
import logging
import time
from typing import Dict, Any, Optional, List
import httpx
from asyncio_throttle import Throttler

from models.schemas import ProcessingError, ErrorCategory
from utils.tracking import rate_limit_tracker, estimate_openai_cost
from config.settings import settings

logger = logging.getLogger(__name__)


class VisionService:
    """Service for integrating with OpenAI Vision API."""
    
    def __init__(self):
        self.api_key = settings.openai_api_key
        self.model = settings.vision_model
        self.max_retries = settings.max_retries
        self.retry_delay = settings.retry_delay
        
        # Rate limiting based on OpenAI best practices
        self.max_requests_per_minute = settings.rate_limit_per_minute
        self.max_tokens_per_minute = 125000  # Conservative estimate for vision models
        self.available_request_capacity = self.max_requests_per_minute
        self.available_token_capacity = self.max_tokens_per_minute
        self.last_update_time = time.time()
        self.seconds_to_pause_after_rate_limit_error = 15
        self.time_of_last_rate_limit_error = 0
        
        # API endpoints
        self.base_url = "https://api.openai.com/v1"
        self.chat_endpoint = f"{self.base_url}/chat/completions"
        
        # Headers for API requests
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
    
    async def process_images(self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process multiple images through Vision API with limited concurrency and rate limiting."""
        results = []
        
        # Process images with limited concurrency (2-3 concurrent requests max)
        max_concurrent = min(3, len(pages))  # Max 3 concurrent requests
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_rate_limiting(page_data: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                # Wait for available capacity before making request
                await self._wait_for_capacity()
                
                # Process single image
                result = await self._process_single_image(page_data)
                
                # Update capacity after request
                self._update_capacity_after_request()
                
                # Brief pause between requests
                await asyncio.sleep(0.001)  # 1ms as recommended in rate_limit.md
                
                return result
        
        # Create tasks for all pages
        tasks = [process_with_rate_limiting(page) for page in pages]
        
        # Process with limited concurrency
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions in results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Failed to process page {pages[i].get('page_id', 'unknown')}: {result}")
                processed_results.append({
                    'page_id': pages[i].get('page_id'),
                    'page_number': pages[i].get('page_number'),
                    'success': False,
                    'error': ProcessingError(
                        page_number=pages[i].get('page_number'),
                        error_category=ErrorCategory.SYSTEM_ERROR,
                        error_message=f"Processing failed: {str(result)}",
                        retry_suggestion="Try again or contact support"
                    ),
                    'extracted_content': None,
                    'raw_response': None,
                    'processing_time': 0.0,
                    'api_cost': 0.0
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _wait_for_capacity(self):
        """Wait until we have sufficient capacity to make a request."""
        while True:
            # Update available capacity
            self._update_available_capacity()
            
            # Check if we have enough capacity (1 request + estimated tokens for vision request)
            estimated_tokens = 1000  # Conservative estimate for vision requests
            
            if (self.available_request_capacity >= 1 and 
                self.available_token_capacity >= estimated_tokens):
                break
            
            # Check if we need to pause due to recent rate limit error
            seconds_since_rate_limit_error = time.time() - self.time_of_last_rate_limit_error
            if seconds_since_rate_limit_error < self.seconds_to_pause_after_rate_limit_error:
                remaining_pause = self.seconds_to_pause_after_rate_limit_error - seconds_since_rate_limit_error
                logger.warning(f"Pausing for {remaining_pause:.1f}s due to recent rate limit error")
                await asyncio.sleep(remaining_pause)
                continue
            
            # Wait a bit before checking again
            await asyncio.sleep(0.1)
    
    def _update_available_capacity(self):
        """Update available request and token capacity based on time elapsed."""
        current_time = time.time()
        seconds_since_update = current_time - self.last_update_time
        
        # Replenish capacity based on time elapsed
        self.available_request_capacity = min(
            self.available_request_capacity + self.max_requests_per_minute * seconds_since_update / 60.0,
            self.max_requests_per_minute
        )
        self.available_token_capacity = min(
            self.available_token_capacity + self.max_tokens_per_minute * seconds_since_update / 60.0,
            self.max_tokens_per_minute
        )
        
        self.last_update_time = current_time
    
    def _update_capacity_after_request(self):
        """Update capacity counters after making a request."""
        estimated_tokens = 1000  # Conservative estimate for vision requests
        self.available_request_capacity -= 1
        self.available_token_capacity -= estimated_tokens
    
    async def _process_single_image(self, page_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single image through Vision API with retry logic."""
        page_id = page_data.get('page_id')
        page_number = page_data.get('page_number')
        image_path = page_data.get('image_path')
        
        start_time = time.time()
        
        for attempt in range(self.max_retries + 1):
            try:
                # Check rate limits
                if not rate_limit_tracker.can_make_request():
                    await asyncio.sleep(1)  # Wait a bit if rate limited
                    continue
                
                # Encode image
                base64_image = self._encode_image(image_path)
                if not base64_image:
                    return self._create_error_result(
                        page_id, page_number, 
                        ErrorCategory.SYSTEM_ERROR,
                        "Failed to encode image",
                        time.time() - start_time
                    )
                
                # Create API request
                payload = self._create_vision_request(base64_image)
                
                # Make API call with extended timeout for Vision API
                async with httpx.AsyncClient(timeout=90.0) as client:
                    response = await client.post(
                        self.chat_endpoint,
                        headers=self.headers,
                        json=payload
                    )
                
                # Record the API call
                rate_limit_tracker.record_request()
                
                if response.status_code == 200:
                    # Success - parse response
                    api_response = response.json()
                    
                    # Extract content
                    extracted_content = self._parse_vision_response(api_response)
                    
                    # Calculate cost
                    api_cost = estimate_openai_cost(self.model, 1)
                    
                    processing_time = time.time() - start_time
                    
                    return {
                        'page_id': page_id,
                        'page_number': page_number,
                        'success': True,
                        'error': None,
                        'extracted_content': extracted_content,
                        'raw_response': api_response if settings.environment == 'development' else None,
                        'processing_time': processing_time,
                        'api_cost': api_cost
                    }
                
                elif response.status_code == 429:
                    # Rate limited - update tracking and wait before retry
                    self.time_of_last_rate_limit_error = time.time()
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Rate limited, waiting {wait_time}s before retry {attempt + 1}")
                    await asyncio.sleep(wait_time)
                    continue
                
                elif response.status_code == 400:
                    # Bad request - don't retry
                    error_msg = f"Bad request: {response.text}"
                    return self._create_error_result(
                        page_id, page_number,
                        ErrorCategory.API_FAILURE,
                        error_msg,
                        time.time() - start_time,
                        "Check image format and size"
                    )
                
                else:
                    # Other API error
                    error_msg = f"API error {response.status_code}: {response.text}"
                    
                    # Handle specific error codes
                    if response.status_code == 502:
                        error_msg = f"OpenAI API server error (502 Bad Gateway): {response.text}"
                        retry_suggestion = "OpenAI servers are experiencing issues, try again in a few minutes"
                    elif response.status_code == 503:
                        error_msg = f"OpenAI API service unavailable (503): {response.text}"
                        retry_suggestion = "OpenAI service is temporarily unavailable, try again later"
                    else:
                        retry_suggestion = "Try again later or contact support"
                    
                    if attempt < self.max_retries:
                        wait_time = self.retry_delay * (2 ** attempt)
                        logger.warning(f"API error {response.status_code}, retrying in {wait_time}s (attempt {attempt + 1})")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        return self._create_error_result(
                            page_id, page_number,
                            ErrorCategory.API_FAILURE,
                            error_msg,
                            time.time() - start_time,
                            retry_suggestion
                        )
            
            except httpx.TimeoutException:
                error_msg = "API request timeout"
                if attempt < self.max_retries:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Timeout, retrying in {wait_time}s (attempt {attempt + 1})")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    return self._create_error_result(
                        page_id, page_number,
                        ErrorCategory.API_FAILURE,
                        error_msg,
                        time.time() - start_time,
                        "Try again with better network connection"
                    )
            
            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                logger.error(f"Unexpected error processing page {page_id}: {e}", exc_info=True)
                if attempt < self.max_retries:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Retrying after unexpected error in {wait_time}s (attempt {attempt + 1})")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    return self._create_error_result(
                        page_id, page_number,
                        ErrorCategory.SYSTEM_ERROR,
                        error_msg,
                        time.time() - start_time
                    )
        
        # If we get here, all retries failed
        return self._create_error_result(
            page_id, page_number,
            ErrorCategory.API_FAILURE,
            "All retry attempts failed",
            time.time() - start_time,
            "Try again later"
        )
    
    def _encode_image(self, image_path: str) -> Optional[str]:
        """Encode image to base64."""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to encode image {image_path}: {e}")
            return None
    
    def _create_vision_request(self, base64_image: str) -> Dict[str, Any]:
        """Create Vision API request payload with expanded schema prompt."""
        return {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """You are an expert document parser for credit underwriting.  
You will receive one or more scanned documents or images. Your job: extract underwriting datapoints into a strict, machine-friendly JSON. Do not add any commentary. Return **valid JSON only**.

### Supported document classes (choose the best fit; if none match, use OTHER)
PAN_FIRM, PAN_INDIVIDUAL, AADHAAR_INDIVIDUAL, UDYAM_REGISTRATION, PARTNERSHIP_DEED,
GST_CERTIFICATE, BANK_STATEMENT, FINANCIAL_STATEMENT, ITR_INDIVIDUAL, ITR_FIRM, OTHER

### RULES (must follow)
1. If multiple files/pages are provided, return an array `documents` where each element follows the schema below.  
2. For every field you extract, include:  
   - `value` (exact text as seen),  
   - `normalized_value` (cleaned type: numbers/dates in canonical format),  
   - `confidence` (0–1),  
   - `source` {file_name, page_number, snippet, bbox? (optional)}.  
3. If a required field is not present, set its value to the string `"INSUFFICIENT_DATA"`. Do NOT guess.  
4. Normalize aggressively: dates → `YYYY-MM-DD`; currency → integer (INR: 1234567); percentages → numeric; names → preserve case but trim whitespace.  
5. Validate identification numbers (PAN / Aadhaar / GST / IFSC) per rules below; if invalid, put `"INVALID"` in `normalized_value`.  
6. For tabular data (statements, financials, invoices) return structured `tables` with `headers`, `rows` (each row as list), and `row_confidences`.  
7. Always include `text_content` (raw OCR text) for the document.

### OUTPUT SCHEMA (strict)
Return a JSON object like this:

{
  "documents": [
    {
      "document_id": "string (optional uuid)",
      "file_name": "string",
      "document_class": "one of the supported classes",
      "entities": {
        "borrower_name": {"value":"...","normalized_value":"...","confidence":0.0,"source":{...}},
        "company_name": {"value":"...","normalized_value":"...","confidence":0.0,"source":{...}},
        "constitution": {"value":"...","normalized_value":"...","confidence":0.0,"source":{...}},
        "registered_address": {"value":"...","normalized_value":"...","confidence":0.0,"source":{...}},
        "pan_number": {"value":"...","normalized_value":"...","confidence":0.0,"source":{...}},
        "gst_number": {"value":"...","normalized_value":"...","confidence":0.0,"source":{...}},
        "aadhaar_number": {"value":"...","normalized_value":"...","confidence":0.0,"source":{...}},
        "udyam_registration_number": {"value":"...","normalized_value":"...","confidence":0.0,"source":{...}},
        "partnership_start_date": {"value":"...","normalized_value":"YYYY-MM-DD","confidence":0.0,"source":{...}},
        "promoters": [
          {
            "name": {"value":"...","normalized_value":"...","confidence":0.0,"source":{...}},
            "pan_number": {...},
            "aadhaar_number": {...},
            "shareholding_percent": {"value":"...","normalized_value":0.0,"confidence":0.0,"source":{...}}
          }
        ],
        "financials": [
          {
            "year": "YYYY",
            "turnover": {"value":"...","normalized_value":0.0,"confidence":0.0,"source":{...}},
            "net_profit": {...},
            "ebitda": {...},
            "total_assets": {...},
            "total_liabilities": {...}
          }
        ],
        "banking": {
          "bank_name": {"value":"...","normalized_value":"...","confidence":0.0,"source":{...}},
          "account_number": {"value":"...","normalized_value":"...","confidence":0.0,"source":{...}},
          "ifsc_code": {"value":"...","normalized_value":"...","confidence":0.0,"source":{...}},
          "avg_monthly_balance": {"value":"...","normalized_value":0.0,"confidence":0.0,"source":{...}}
        },
        "top_suppliers": [{"name":{...},"amount":{...},"percent_of_purchases":{...}}],
        "top_buyers": [{"name":{...},"amount":{...},"percent_of_sales":{...}}],
        "itr_assessment_year": {"value":"...","normalized_value":"YYYY","confidence":0.0,"source":{...}},
        "other_fields": {}
      },
      "tables": [
        {
          "title": "string or INSUFFICIENT_DATA",
          "headers": ["..."],
          "rows": [["col1","col2",12345]],
          "row_confidences": [0.9]
        }
      ],
      "text_content": "full raw OCR text",
      "overall_confidence": 0.0
    }
  ]
}"""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 4096,
            "temperature": 0.1
        }
    
    def _parse_vision_response(self, api_response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Vision API response and extract structured data."""
        try:
            # Get the response content
            content = api_response['choices'][0]['message']['content']
            
            # Clean up the content - remove markdown code blocks if present
            cleaned_content = content.strip()
            if cleaned_content.startswith('```json'):
                # Remove ```json from start and ``` from end
                cleaned_content = cleaned_content[7:]  # Remove ```json
                if cleaned_content.endswith('```'):
                    cleaned_content = cleaned_content[:-3]  # Remove ```
                cleaned_content = cleaned_content.strip()
            elif cleaned_content.startswith('```'):
                # Remove generic ``` blocks
                lines = cleaned_content.split('\n')
                if lines[0].strip() == '```' and lines[-1].strip() == '```':
                    cleaned_content = '\n'.join(lines[1:-1])
                elif lines[-1].strip() == '```':
                    cleaned_content = '\n'.join(lines[:-1])
                    if cleaned_content.startswith('```'):
                        cleaned_content = cleaned_content[3:]
                cleaned_content = cleaned_content.strip()
            
            # Try to parse as JSON
            try:
                extracted_data = json.loads(cleaned_content)
                
                # Validate that it follows the new schema structure
                if "documents" in extracted_data and isinstance(extracted_data["documents"], list):
                    logger.info(f"Successfully parsed Vision API response with {len(extracted_data['documents'])} documents")
                    return extracted_data
                else:
                    # If it's not in the expected format, wrap it in the new schema
                    logger.warning("Vision API response not in expected schema format, wrapping in new structure")
                    return {
                        "documents": [{
                            "document_id": None,
                            "file_name": "unknown",
                            "document_class": "OTHER",
                            "entities": {},
                            "tables": extracted_data.get("tables", []),
                            "text_content": extracted_data.get("text_content", content),
                            "overall_confidence": 0.5
                        }]
                    }
                    
            except json.JSONDecodeError as e:
                # If not valid JSON, return in new schema format with raw text
                logger.warning(f"Vision API returned non-JSON response: {e}")
                logger.debug(f"Cleaned content that failed to parse: {cleaned_content[:500]}...")
                return {
                    "documents": [{
                        "document_id": None,
                        "file_name": "unknown",
                        "document_class": "OTHER",
                        "entities": {},
                        "tables": [],
                        "text_content": content,
                        "overall_confidence": 0.1
                    }]
                }
        
        except Exception as e:
            logger.error(f"Failed to parse Vision API response: {e}")
            return {
                "documents": [{
                    "document_id": None,
                    "file_name": "unknown",
                    "document_class": "OTHER",
                    "entities": {},
                    "tables": [],
                    "text_content": "Failed to parse response",
                    "overall_confidence": 0.0
                }]
            }
    
    def _create_error_result(self, page_id: str, page_number: int, 
                           error_category: ErrorCategory, error_message: str,
                           processing_time: float, retry_suggestion: str = None) -> Dict[str, Any]:
        """Create error result for failed processing."""
        return {
            'page_id': page_id,
            'page_number': page_number,
            'success': False,
            'error': ProcessingError(
                page_number=page_number,
                error_category=error_category,
                error_message=error_message,
                retry_suggestion=retry_suggestion
            ),
            'extracted_content': None,
            'raw_response': None,
            'processing_time': processing_time,
            'api_cost': 0.0
        }
