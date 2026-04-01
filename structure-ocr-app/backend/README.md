# Structure-OCR Backend

FastAPI backend for document text extraction and approximate structure reconstruction.

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

## API

- `GET /health`
- `POST /api/extract` with `multipart/form-data` file upload
