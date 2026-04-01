from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_extract_empty_file_rejected() -> None:
    response = client.post(
        "/api/extract",
        files={"file": ("empty.pdf", BytesIO(b""), "application/pdf")},
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "empty file"}


def test_extract_unsupported_file_type_rejected() -> None:
    response = client.post(
        "/api/extract",
        files={"file": ("doc.docx", BytesIO(b"fake docx content"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert response.status_code == 400
    body = response.json()
    assert "unsupported file type" in body["detail"]


def test_extract_txt_file_returns_text() -> None:
    content = b"Hello, this is a test document."
    response = client.post(
        "/api/extract",
        files={"file": ("test.txt", BytesIO(content), "text/plain")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "test.txt"
    assert body["text"] == "Hello, this is a test document."
    assert body["pages"] == 1
    assert len(body["blocks"]) == 1
    assert body["blocks"][0]["type"] == "text"
    assert body["checksum"]


def test_extract_invalid_pdf_file_returns_graceful_error() -> None:
    content = b"%PDF-1.4\n%fake pdf content"
    response = client.post(
        "/api/extract",
        files={"file": ("test.pdf", BytesIO(content), "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "test.pdf"
    assert body["pages"] == 0
    assert len(body["notes"]) > 0
    assert "corrupted" in body["notes"][0].lower() or "could not open" in body["notes"][0].lower()


def test_extract_invalid_image_file_returns_graceful_error() -> None:
    content = b"not a real image"
    response = client.post(
        "/api/extract",
        files={"file": ("test.png", BytesIO(content), "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "test.png"
    assert body["pages"] == 0
    assert len(body["notes"]) > 0
