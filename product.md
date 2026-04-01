# Product Brief

## Product Name

Structure-OCR

## One Sentence

A simple web app that accepts text, photos, images, and PDFs, then uses PaddleOCR to extract document text and preserve the original layout as faithfully as possible.

## Problem

Users need a lightweight way to upload documents and get back readable text plus structure-aware output without manually copying content.

## Target Users

- Internal operators
- Analysts
- Legal or operations staff
- Anyone who needs fast document transcription with layout preservation

## Core Outcome

The app should turn a single uploaded file into:

- extracted plain text
- page-level structure blocks
- reading order information
- bounding boxes when available
- confidence data when available

## Non-Goals

- Perfect reconstruction for every document
- Human correction workflows
- Multi-user permissions
- Long-term document storage
- Search, tagging, or OCR review queues

## Product Rules

- Keep the first version small
- Prefer a single upload flow
- Prefer deterministic output formats
- Preserve structure metadata whenever the OCR engine can provide it
- Fail gracefully when a document is too low quality

## Success Criteria

- Upload works for PDF and image files
- The backend returns structured JSON
- The frontend can show raw text and structured blocks
- The system is easy to run locally
- The system is easy to extend later
