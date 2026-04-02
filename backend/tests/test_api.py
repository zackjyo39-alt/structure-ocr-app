from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient

from app.ocr import _normalize_pdf_line_breaks
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


def test_normalize_pdf_line_breaks_merges_fragmented_abbreviation_lines() -> None:
    raw_text = "\n".join(
        [
            "驻车制动器................16",
            "发动机控制系统和燃油系统................17",
            "1.0",
            "1.0升（L5Q",
            "L5Q",
            "L5Q LE1",
            "LE1",
            "LE1 LWT",
        ]
    )

    normalized = _normalize_pdf_line_breaks(raw_text)
    lines = normalized.splitlines()

    assert lines[0] == "驻车制动器................16"
    assert lines[1] == "发动机控制系统和燃油系统................17"
    assert lines[2] == "1.0 1.0升（L5Q L5Q L5Q LE1 LE1 LE1 LWT"


def test_normalize_pdf_line_breaks_skips_blank_between_title_and_fragment() -> None:
    raw_text = "发动机控制系统和燃油系统－1.0\n\n1.0\n1.0升（L5Q\nL5Q"
    normalized = _normalize_pdf_line_breaks(raw_text)
    assert "\n\n" not in normalized
    assert "发动机控制系统和燃油系统－1.0 1.0 1.0升（L5Q L5Q" in normalized


def test_normalize_pdf_line_breaks_blank_does_not_merge_two_toc_titles() -> None:
    raw_text = "一般信息\n\n振动诊断和校正................................................................... 4"
    normalized = _normalize_pdf_line_breaks(raw_text)
    lines = normalized.splitlines()
    assert lines[0] == "一般信息"
    assert lines[1].startswith("振动诊断和校正")
