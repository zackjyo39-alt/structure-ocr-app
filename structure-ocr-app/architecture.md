# Architecture

## System Overview

This product uses a two-service layout:

- frontend: React app for upload and result display
- backend: FastAPI app for file parsing and OCR extraction

The frontend never performs OCR directly. All extraction happens in the backend.

The first UI version follows a workspace pattern:

- fixed sidebar
- top header
- split content area
- floating action buttons

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

Each block should contain:

- page
- type
- text
- bbox when available
- confidence when available

The frontend should map these blocks into a hierarchical layout view and a raw text view.

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

- background jobs
- persistent storage
- document history
- authentication
- better page preview
- block highlighting
- export to DOCX/HTML/JSON

