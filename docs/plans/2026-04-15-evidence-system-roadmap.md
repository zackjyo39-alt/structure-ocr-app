# Evidence System Roadmap

## North Star

Build this project into an evidence information system for judges and lawyers.

The system should eventually support the "要件审判九步法" by helping operators:

- extract evidence-bearing facts from raw legal materials
- understand which evidence supports which legal elements
- identify contradictions and weak links
- see what evidence or data is still missing
- support legal application and reasoned adjudication drafting

## Guiding Principle

Do not try to jump from OCR directly to final legal reasoning.

Build upward through stable intermediate layers:

1. OCR / layout
2. evidence items
3. legal element mapping
4. evidence chain completeness
5. adjudication support

Each phase should be usable on its own.

## Current State

The project already has:

- OCR and structure extraction
- VLM-assisted extraction path
- review notes and confidence signals
- initial `evidence_items` output and frontend evidence tab

This means the project has moved from a pure OCR viewer toward an evidence extraction workspace.

## Phase Plan

### Phase 1: OCR Foundation

Goal:
- convert legal materials into text, blocks, coordinates, and reviewable extraction output

Done / in progress:
- upload and parse PDF/image/text
- OCR blocks and structure blocks
- confidence, notes, and cross-validation output

### Phase 2: Evidence Item Extraction

Goal:
- produce source-grounded evidence units from OCR/VLM output

Current slice:
- derive case numbers
- derive amounts
- derive dates
- derive parties
- derive fact fragments
- mark evidence needing review

Next hardening tasks:
- improve party extraction quality
- add contract numbers, account numbers, stamp/signature evidence
- reduce duplicate evidence items
- add evidence type tests per document class

### Phase 3: Legal Element Mapping

Goal:
- map evidence items to elements of a specific cause of action

Implementation rule:
- start with one narrow case type only

Recommended first domain:
- loan / debt dispute

Target outputs:
- element name
- supporting evidence items
- conflicting evidence items
- missing evidence
- operator review notes

### Phase 4: Evidence Chain Analysis

Goal:
- connect claim, fact, evidence, contradiction, and missing link

Target outputs:
- chain completeness status
- chain weak points
- contradiction alerts
- supplementary evidence checklist

### Phase 5: Adjudication Support

Goal:
- help generate structured legal-analysis outputs without hiding uncertainty

Target outputs:
- legal application summary
- fact-finding support
- reasoning draft scaffold
- explicit "cannot establish due to missing evidence" explanations

## Session-by-Session Delivery Rule

Each session should focus on one clear vertical slice only.

### Now

- stabilize `evidence_items`
- make the evidence tab more useful for legal review

### Next

- choose one case type
- define its legal elements
- add `element_mapping` output in backend and frontend

### Later

- build evidence-chain graph and missing-evidence checklist
- add adjudication-support views

## Data Contract Direction

The likely backend response layers will grow toward:

- `text`
- `blocks`
- `evidence_items`
- `element_mappings`
- `evidence_chain`
- `missing_evidence`
- `adjudication_support`

Each new layer should remain reviewable and source-grounded.

## Non-Negotiables

- Do not remove source provenance from legal outputs
- Do not present unsupported legal conclusions as facts
- Do not skip intermediate layers just to get "smart" demos
- Do not expand scope horizontally before the current vertical slice is stable
