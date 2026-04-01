# UI Spec

## Screen 1: Workspace

### Purpose

Provide a single working surface for document upload, OCR processing, and structured result review.

### Layout

- Full-screen dark workspace
- Fixed left navigation sidebar
- Top header bar
- Split main canvas with:
  - large source preview area on the left
  - structured result panel on the right
- Floating primary action button near the bottom center
- Floating export button near the bottom right

### Sidebar Content

- Project title and tier label
- Primary action: `New Extraction`
- Navigation items:
  - Workspace
  - History
  - Templates
  - API Keys
  - Help
  - Logout

### Header Content

- Product title: `Structure-OCR`
- Top navigation links:
  - Backend Config
  - Status
  - Documentation
- Settings and notification actions
- User profile avatar

### Left Panel

- Large dashed upload canvas
- Document preview area
- OCR overlay boxes for detected regions
- Hover state that encourages drag-and-drop upload
- Footer metadata showing:
  - engine status
  - confidence score
  - source filename

### Right Panel

- Tabbed result view
- Tabs:
  - Layout View
  - Raw Text
  - Table/Excel
- Hierarchical cards for detected content types:
  - Title
  - Paragraph
  - Table
  - Image / entity
- Confidence badges for structure results
- Per-item action buttons such as edit, expand, or open
- Footer export area with JSON output action

### Floating Actions

- Primary action button:
  - `Process Document`
- Contextual export button:
  - `Export to Excel`

### Visual Style

- Dark theme
- Glassmorphism panels
- Soft borders
- High contrast text
- Blue/purple accent for primary actions
- Warm accent for table/secondary structure types

### Interaction Rules

- Hovering the upload area reveals the drop-state CTA
- The left preview should show OCR bounding overlays when extraction is complete
- The right panel should switch between layout, text, and table views
- Export actions should be available after successful extraction

