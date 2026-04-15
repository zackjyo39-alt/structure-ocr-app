from __future__ import annotations

from io import BytesIO

import numpy as np
from PIL import Image
from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app
from app.ocr import _OcrEngineWrapper, _normalize_pdf_line_breaks, _rapidocr_raw_list
from app.validation import compute_legal_field_diffs_for_page
from app.vlm import normalize_gemini_base_url

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


def test_extract_txt_file_derives_evidence_items() -> None:
    content = (
        "原告：张三\n"
        "被告：李四\n"
        "案号：（2024）京0105民初1234号\n"
        "签约日期：2024年3月5日\n"
        "争议金额：¥12345.50元\n"
    ).encode("utf-8")
    response = client.post(
        "/api/extract",
        files={"file": ("evidence.txt", BytesIO(content), "text/plain")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["evidence_items"]
    types = {item["evidence_type"] for item in body["evidence_items"]}
    assert "party" in types
    assert "case_number" in types
    assert "date" in types
    assert "amount" in types


def test_extract_rejects_oversized_file(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "MAX_FILE_SIZE_MB", 1)
    content = b"x" * (2 * 1024 * 1024)
    response = client.post(
        "/api/extract",
        files={"file": ("too-large.txt", BytesIO(content), "text/plain")},
    )
    assert response.status_code == 413
    assert "exceeds maximum 1MB" in response.json()["detail"]


def test_rapidocr_raw_list_accepts_numpy_arrays() -> None:
    class FakeRapidOCRResult:
        boxes = np.array([[[0, 0], [10, 0], [10, 10], [0, 10]]], dtype=float)
        txts = np.array(["hello"])
        scores = np.array([0.95], dtype=float)

    rows = _rapidocr_raw_list(FakeRapidOCRResult())
    assert len(rows) == 1
    assert rows[0][1][0] == "hello"
    assert rows[0][1][1] == 0.95


def test_apple_vision_wrapper_uses_callable_ocrmac_api() -> None:
    called = {"detail": None}

    def fake_text_from_image(image, detail=True):
        called["detail"] = detail
        return [("hello", 0.88, (0.1, 0.2, 0.3, 0.1))]

    wrapper = _OcrEngineWrapper("apple_vision", fake_text_from_image)
    image = Image.new("RGB", (100, 80), color="white")
    blocks, text = wrapper.predict(np.zeros((80, 100, 3), dtype=np.uint8), image)
    assert called["detail"] is True
    assert text == "hello"
    assert len(blocks) == 1


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


def test_legal_field_diffs_case_match_with_punctuation_normalize() -> None:
    vlm = "案件 (2023)京0105民初1234号 终结"
    ocr = "案件 （2023）京0105民初1234号 终结"
    d = compute_legal_field_diffs_for_page(vlm, ocr, page=1)
    assert d["ocr_unavailable"] is False
    assert d["has_discrepancy"] is False
    assert len(d["case_numbers"]) == 1
    assert d["case_numbers"][0]["status"] == "match"


def test_legal_field_diffs_case_vlm_only() -> None:
    vlm = "(2024)粤01民终999号"
    ocr = "(2023)粤01民终999号"
    d = compute_legal_field_diffs_for_page(vlm, ocr, page=1)
    assert d["has_discrepancy"] is True
    statuses = {r["status"] for r in d["case_numbers"]}
    assert "vlm_only" in statuses
    assert "ocr_only" in statuses


def test_legal_field_diffs_amount_match() -> None:
    vlm = "判赔 12,345.50 元"
    ocr = "判赔 ¥12345.50元"
    d = compute_legal_field_diffs_for_page(vlm, ocr, page=1)
    assert d["has_discrepancy"] is False
    assert any(r["status"] == "match" for r in d["amounts"])


def test_normalize_gemini_base_url_defaults_and_strips_models_path() -> None:
    assert normalize_gemini_base_url("") == "https://generativelanguage.googleapis.com/v1beta"
    assert normalize_gemini_base_url("https://generativelanguage.googleapis.com/v1") == "https://generativelanguage.googleapis.com/v1"
    pasted = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash"
    assert normalize_gemini_base_url(pasted) == "https://generativelanguage.googleapis.com/v1beta"


def test_normalize_pdf_line_breaks_blank_does_not_merge_two_toc_titles() -> None:
    raw_text = "一般信息\n\n振动诊断和校正................................................................... 4"
    normalized = _normalize_pdf_line_breaks(raw_text)
    lines = normalized.splitlines()
    assert lines[0] == "一般信息"
    assert lines[1].startswith("振动诊断和校正")
