# Requirements

## North Star

This project is no longer only an OCR app.

Its long-term goal is to become an evidence information system for judges and lawyers that can:

- extract evidence-bearing facts from legal materials
- organize those facts into evidence chains
- support the "要件审判九步法"
- explain which legal elements are already supported
- identify what data or evidence is still missing

All implementation should move toward that goal in small vertical slices.

## Functional Requirements

### Upload

- Users can upload a single file at a time
- Supported file types:
  - PDF
  - PNG
  - JPG
  - JPEG
  - WebP
  - text files
- The UI must reject unsupported file types

### Extraction

- The backend must detect whether the input is a PDF, image, or text file
- The backend must extract text from the file
- The backend must preserve page-level structure metadata when possible
- The backend must emit:
  - page number
  - block type
  - extracted text
  - bounding box when available
  - confidence when available

### Evidence Extraction

- The backend must be able to derive reviewable `evidence_items` from extracted blocks
- Each evidence item must preserve source provenance:
  - source page
  - source text
  - source block reference when available
- Each evidence item should include normalized legal signals when detectable:
  - case number
  - amount
  - date
  - party
  - fact fragment
- The system must mark evidence items that need review
- The system should expose missing fields for incomplete evidence items

### Legal Analysis Direction

- The system must evolve toward cause-of-action-specific legal element mapping
- The system must eventually distinguish:
  - supported elements
  - partially supported elements
  - unsupported elements
- The system must eventually report missing evidence needed to complete an element chain
- The system must never present unsupported legal conclusions as certain facts

### Display

- The frontend must show the extracted text
- The frontend must show structured block output
- The frontend must show extracted evidence items
- The frontend must show file metadata such as filename and checksum
- The frontend must show errors in a readable way

### Workspace UI

- The application must use a dark workspace layout
- The application must show a fixed left sidebar for navigation
- The application must show a top header with product title and utility links
- The application must show a split view:
  - left document preview / upload canvas
  - right structured results panel
- The application must include a primary `Process Document` action
- The application must include an export action for structured output
- The application must support a tabbed result panel:
  - layout view
  - evidence view
  - raw text
  - table/export view
- The application must visually highlight detected OCR regions on the preview canvas
- The application must show confidence and source metadata in the workspace footer
- The application should make review-needed evidence visually obvious

## Quality Requirements

- The system should degrade gracefully if OCR libraries are not installed
- The API should return stable JSON
- The API should preserve backward compatibility when new intermediate fields are added
- The backend should not require a database in the first version
- The app should run locally with separate frontend and backend processes
- Intermediate evidence structures should be deterministic enough for human audit

## Out of Scope for First Version

- Authentication
- Authorization
- Persistent job queues
- Background workers
- Multi-file batch upload
- Human correction interface
- Production scaling
- Full legal reasoning automation across all causes of action
- Automatic final adjudication without human review

## UI Out of Scope for First Version

- Real-time collaboration
- Multi-document workspace
- Custom theme editor
- Dragging panels to re-layout the page
- Advanced annotation tools

## Acceptance Criteria

- Uploading a supported file returns a successful JSON response
- Uploading an empty file returns a clear error
- Uploading an unsupported file returns a clear error
- The frontend can display the backend response without manual conversion
- The project can be started locally by following the README
- The workspace layout matches the split-view dark UI direction from the provided Stitch design
- The project can expose at least one legally meaningful intermediate layer beyond OCR text
