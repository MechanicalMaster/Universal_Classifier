Perfect — thanks for clarifying ✅.
Given your answers, here’s the **final implementation plan** for updating your **Vision API prompt** across the codebase.

---

# Implementation Plan: Vision API Prompt Update

## 1. Locate and Update Prompt Construction

* **Files impacted**:

  * `services/document_processing_service.py` (look for `_create_vision_request`).
  * Any central **prompt definitions** file (e.g., `prompts/vision_prompt.txt`, if exists).

* **Change**:

  * Replace the current generic prompt (`document_type`, `key_information`, etc.) with the new **expanded schema prompt** we finalized (with `document_class`, `entities`, `tables`, `text_content`).
  * Ensure the prompt explicitly lists all supported classes:
    `PAN_FIRM, PAN_INDIVIDUAL, AADHAAR_INDIVIDUAL, UDYAM_REGISTRATION, PARTNERSHIP_DEED, GST_CERTIFICATE, BANK_STATEMENT, FINANCIAL_STATEMENT, ITR_INDIVIDUAL, ITR_FIRM, OTHER`.
  * Remove references to old fields (`key_information`) from the prompt text.
  * Keep JSON output requirement strict: `"Return only valid JSON"`.

---

## 2. Update Data Aggregation Logic

* **Files impacted**:

  * `services/data_aggregator.py` (responsible for combining per-page or per-doc Vision outputs).
  * Any helper classes that previously used `key_information` or `document_type`.

* **Change**:

  * Refactor aggregation to parse from `documents[].entities` instead of `key_information`.
  * Store `document_class` and `entities` directly for downstream consumption.
  * Retain `tables` and `text_content` fields from the new schema.

---

## 3. Remove Legacy Schema References

* **Files impacted**:

  * `models/document_models.py` or `schemas/document_schema.py` (if type definitions exist).
  * Any internal DTOs or mappings in `services/vision_service.py`.

* **Change**:

  * Remove fields: `document_type`, `key_information`.
  * Add/align to new fields: `document_class`, `entities`, `tables`, `text_content`.

---

## 4. Underwriting Service Adjustments

* **Files impacted**:

  * `services/underwriting_service.py` (or wherever Vision JSON is passed into the underwriting prompt).
  * `prompts/underwriting_prompt.txt`.

* **Change**:

  * Ensure underwriting logic references `entities` directly (e.g., `pan_number`, `aadhaar_number`, `financials[]`) instead of old free-form keys.
  * Confirm that `OTHER` document\_class is gracefully handled (ignored or stored as supplemental evidence).

---

## 5. Testing & Verification

* **Files impacted**:

  * `tests/test_document_processing.py`
  * `tests/test_data_aggregator.py`

* **Change**:

  * Update test mocks to produce Vision responses in the **new schema format**.
  * Remove tests expecting `key_information`.
  * Add new tests for each document\_class type.
  * Add assertions that required normalization (e.g., PAN regex, Aadhaar 12-digit, GST 15-char) flows correctly into the `entities`.

---

