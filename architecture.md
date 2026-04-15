# Architecture

## System Overview

This product uses a two-service layout:

- frontend: React app for upload and result display
- backend: FastAPI app for file parsing and OCR extraction

The frontend never performs OCR directly. All extraction and legal-analysis preprocessing happen in the backend.

The current UI follows a workspace pattern:

- fixed sidebar
- top header
- split content area
- floating action buttons

The architectural direction is a layered legal-analysis pipeline:

`source materials -> OCR / layout -> evidence items -> legal element mapping -> evidence chain analysis -> adjudication support`

## Components

### Frontend

- React
- Vite
- Single-page upload interface
- Result rendering for raw text and structured JSON
- Workspace shell that matches the dark split-view Stitch direction
- OCR preview overlay rendering
- Tabbed result panel
- Export action area

### Backend

- FastAPI
- Multipart file upload endpoint
- File-type detection
- PDF parsing with PyMuPDF
- OCR via PaddleOCR
- Structure extraction via PaddleOCR structure pipeline when available
- Evidence-item derivation as a post-extraction layer
- Future legal-element and evidence-chain analysis layers

### OCR Strategy

- For PDFs:
  - try native text extraction first
  - fall back to rendered page images
  - use structure-aware extraction when available
  - fall back to OCR if needed
- For images:
  - run OCR directly
- For text files:
  - decode and return the text directly

## Output Contract

The backend returns JSON with:

- filename
- mime_type
- checksum
- pages
- text
- blocks
- notes
- evidence_items

Each block should contain:

- page
- type
- text
- bbox when available
- confidence when available

The frontend should map these blocks into a hierarchical layout view and a raw text view.

The next layers should map the same backend response into:

- evidence review views
- legal-element mapping views
- missing-evidence guidance views

## Failure Strategy

- If PaddleOCR is missing, return a graceful note instead of crashing
- If a page cannot be parsed, continue with the remaining pages
- If structure extraction fails, fall back to OCR
- If OCR fails, return notes with the failure reason

## Run Model

- Backend runs on port `8000`
- Frontend runs on port `5173`
- Frontend calls backend via HTTP

## Extensibility

Later versions can add:

- cause-of-action-specific legal schemas
- legal element mapping
- evidence chain graphing
- contradiction detection
- missing-evidence checklists
- draft adjudication / reasoning support
- background jobs
- persistent storage
- document history
- authentication
- better page preview
- export to DOCX/HTML/JSON

## Current Vertical Slice Strategy

Implementation should proceed in small, testable slices:

1. OCR and structure extraction
2. Evidence-item extraction
3. Element mapping for a narrow legal domain
4. Evidence chain completeness analysis
5. Decision-support outputs

Each slice must leave behind a stable intermediate contract that the next slice can build on.
