# Product Brief

## Product Name

Structure-OCR

## One Sentence

An evidence-oriented legal document analysis workspace that starts from OCR, then builds toward evidence extraction, element-by-element adjudication support, and explicit missing-evidence guidance for judges and lawyers.

## Problem

Judges and lawyers do not ultimately need OCR output. They need a system that can:

- read fragmented legal materials
- extract evidence-bearing facts
- organize those facts into evidence chains
- map evidence to legal elements
- surface contradictions, weak links, and missing proof
- support the "要件审判九步法" workflow with concrete, reviewable analysis

Plain text extraction is only the first layer of that system.

## Target Users

- Judges
- Lawyers
- Legal assistants
- Internal analysts handling evidence-heavy case files

## Core Outcome

The system should progressively turn uploaded case materials into:

- extracted plain text
- page-level structure blocks
- evidence items with page/source grounding
- legal-element-oriented evidence mapping
- evidence chain completeness analysis
- explicit missing-evidence prompts
- draftable reasoning support for legal application and adjudication

## Non-Goals

- Fully autonomous legal judgment without human review
- Silent rewriting of evidence or facts
- Promise of perfect reconstruction for every source document
- Full case management, permissions, or litigation workflow in the first stages
- Long-term storage and multi-tenant infrastructure in the first stages

## Product Rules

- Keep each implementation session to one verifiable vertical slice
- Treat OCR as an input layer, not the final product
- Prefer evidence-grounded output over free-form legal chat
- Preserve page/source provenance for every extracted evidence unit
- Make missing data explicit instead of hiding uncertainty
- Prefer deterministic intermediate structures that can be audited by humans
- Fail gracefully when a document is too low quality or a legal conclusion cannot be supported

## Success Criteria

- The system can ingest legal materials locally
- The backend returns stable, reviewable intermediate JSON structures
- The frontend can show OCR blocks and evidence items side by side
- Each phase adds a usable legal-analysis capability without breaking the previous layer
- The system can eventually tell the operator what evidence is present, what is weak, and what is still missing

## Product Phases

### Phase 1: OCR Foundation

- text extraction
- structure blocks
- page grounding
- confidence and review notes

### Phase 2: Evidence Extraction

- derive `evidence_items` from OCR / VLM output
- capture amounts, dates, case numbers, parties, and fact fragments
- highlight review-needed evidence units

### Phase 3: Element Mapping

- map evidence items to legal elements for a selected cause of action
- show which elements are supported, partially supported, or unsupported

### Phase 4: Evidence Chain Analysis

- connect claims, facts, evidence, contradictions, and missing links
- generate missing-evidence checklists

### Phase 5: Adjudication Support

- support legal application analysis
- support reasoned decision drafting
- support explicit explanation of what facts still cannot be established
