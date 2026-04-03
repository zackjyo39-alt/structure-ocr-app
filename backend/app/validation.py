"""
Validation layer for legal document OCR extraction.

Provides:
  - Dual-Engine Consensus: compare VLM vs PaddleOCR outputs
  - Legal field regex validation: case numbers, dates, amounts
  - Per-block confidence scoring (replaces hardcoded 1.0)
"""

from __future__ import annotations

import re
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Legal field regex patterns
# ---------------------------------------------------------------------------

# 案号 patterns: (2023)京0105民初1234号, （2023）粤03民终567号
_CASE_NUMBER_RE = re.compile(
    r"[\(（](\d{4})[\)）]"           # year
    r"([\u4e00-\u9fa5]{1,3})"        # province/court abbreviation
    r"(\d{1,6})"                      # court code
    r"([\u4e00-\u9fa5]{1,5})"        # case type (民初, 民终, 刑初, etc.)
    r"(\d+)"                          # case sequence number
    r"号"
)

# Date patterns
_DATE_YEAR_MONTH_DAY_RE = re.compile(
    r"(\d{4})年(\d{1,2})月(\d{1,2})日"
)
_DATE_ISO_RE = re.compile(
    r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})"
)

# Amount patterns
_AMOUNT_YUAN_RE = re.compile(
    r"(?:¥|￥)?(\d[\d,]*(?:\.\d{1,2})?)\s*元"
)
_AMOUNT_YUAN_DECIMAL_RE = re.compile(
    r"(?:¥|￥)(\d[\d,]*(?:\.\d{1,2})?)"
)

# Legal field group_ids that the VLM prompt uses
_LEGAL_GROUP_IDS = {
    "court_name", "case_number", "parties_info", "cause_of_action",
    "fact_and_reasons", "court_ruling", "stamp_signature",
}

# Valid Chinese province/court codes (partial list of common ones)
_VALID_PROVINCE_CODES = {
    "京", "津", "沪", "渝", "冀", "豫", "云", "辽", "黑", "湘",
    "皖", "鲁", "新", "苏", "浙", "赣", "鄂", "桂", "甘", "晋",
    "蒙", "陕", "吉", "闽", "贵", "粤", "青", "藏", "川", "宁",
    "琼", "港", "澳", "台",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_legal_fields(blocks: list[dict]) -> list[str]:
    """Scan blocks for legal field patterns and return warnings for suspicious values."""
    warnings: list[str] = []

    for block in blocks:
        text = block.get("text", "")
        if not text:
            continue

        # --- Case number validation ---
        for m in _CASE_NUMBER_RE.finditer(text):
            year = int(m.group(1))
            province = m.group(2)
            court_code = m.group(3)
            case_type = m.group(4)

            current_year = 2026
            if year < 1950 or year > current_year + 1:
                warnings.append(
                    f"案号年份异常: 「{m.group(0)}」中的年份 {year} 不在合理范围内"
                )
            if province not in _VALID_PROVINCE_CODES:
                warnings.append(
                    f"案号地区代码异常: 「{m.group(0)}」中的「{province}」不是标准地区代码"
                )

        # --- Date validation ---
        for m in _DATE_YEAR_MONTH_DAY_RE.finditer(text):
            year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if month < 1 or month > 12:
                warnings.append(
                    f"日期月份异常: 「{m.group(0)}」中的月份 {month} 超出范围"
                )
            if day < 1 or day > 31:
                warnings.append(
                    f"日期天数异常: 「{m.group(0)}」中的日期 {day} 超出范围"
                )

        for m in _DATE_ISO_RE.finditer(text):
            year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if month < 1 or month > 12:
                warnings.append(
                    f"日期月份异常: 「{m.group(0)}」中的月份 {month} 超出范围"
                )
            if day < 1 or day > 31:
                warnings.append(
                    f"日期天数异常: 「{m.group(0)}」中的日期 {day} 超出范围"
                )

        # --- Amount validation ---
        for m in _AMOUNT_YUAN_RE.finditer(text):
            amount_str = m.group(1).replace(",", "")
            try:
                amount = float(amount_str)
                if amount > 1_000_000_000:  # > 1 billion
                    warnings.append(
                        f"金额异常: 「{m.group(0)}」金额过大 ({amount:,.2f}元)，建议复核"
                    )
            except ValueError:
                pass

        for m in _AMOUNT_YUAN_DECIMAL_RE.finditer(text):
            amount_str = m.group(1).replace(",", "")
            try:
                amount = float(amount_str)
                if amount > 1_000_000_000:
                    warnings.append(
                        f"金额异常: 「{m.group(0)}」金额过大 ({amount:,.2f}元)，建议复核"
                    )
            except ValueError:
                pass

    # Deduplicate warnings
    return list(dict.fromkeys(warnings))


def compute_consensus_score(
    vlm_blocks: list[dict],
    ocr_blocks: list[dict],
    ocr_text: str | None = None,
) -> dict:
    """Compare VLM output with PaddleOCR output for consensus checking.

    Returns dict with text_similarity, block_count_ratio, and warnings.
    """
    warnings: list[str] = []

    # Combine VLM text
    vlm_text = " ".join(b.get("text", "") for b in vlm_blocks if b.get("text"))

    # Combine OCR text
    if ocr_text:
        combined_ocr = ocr_text
    else:
        combined_ocr = " ".join(b.get("text", "") for b in ocr_blocks if b.get("text"))

    # Jaccard similarity on character bigrams
    text_similarity = _jaccard_bigram_similarity(vlm_text, combined_ocr) if combined_ocr else 0.0

    # Block count ratio
    ocr_block_count = len(ocr_blocks) if ocr_blocks else 0
    if ocr_block_count > 0:
        block_ratio = len(vlm_blocks) / ocr_block_count
    else:
        block_ratio = float(len(vlm_blocks)) if vlm_blocks else 1.0

    if text_similarity < 0.5 and combined_ocr.strip():
        warnings.append(
            f"VLM 提取文本与 PaddleOCR 结果差异较大 (相似度 {text_similarity:.0%})，建议人工复核"
        )

    if block_ratio < 0.3 and ocr_block_count > 5:
        warnings.append(
            f"VLM 提取的块数 ({len(vlm_blocks)}) 远少于 OCR ({ocr_block_count})，可能存在遗漏"
        )
    elif block_ratio > 3.0 and ocr_block_count > 2:
        warnings.append(
            f"VLM 提取的块数 ({len(vlm_blocks)}) 远多于 OCR ({ocr_block_count})，可能存在过度分割"
        )

    return {
        "text_similarity": round(text_similarity, 4),
        "block_count_ratio": round(block_ratio, 4),
        "warnings": warnings,
    }


def compute_vlm_confidence(
    block: dict,
    ocr_blocks: list[dict] | None = None,
    ocr_text: str | None = None,
) -> float:
    """Compute a confidence score for a single VLM block.

    Scoring:
      - Base: 0.85
      - +0.10 if block text appears in OCR text (substring match)
      - +0.05 if block has a legal field group_id
      - -0.15 if block has no bbox
      - 0.0 if block text is empty
    """
    text = block.get("text", "")
    if not text or not text.strip():
        return 0.0

    confidence = 0.85

    # Substring match against OCR text
    if ocr_text and text.strip() in ocr_text:
        confidence += 0.10
    elif ocr_text:
        # Partial match: check if > 60% of words appear
        vlm_words = set(text.strip())
        ocr_words = set(ocr_text)
        if vlm_words and len(vlm_words & ocr_words) / len(vlm_words) > 0.6:
            confidence += 0.05

    # Legal field bonus
    group_id = block.get("group_id", "")
    if group_id in _LEGAL_GROUP_IDS:
        confidence += 0.05

    # No spatial grounding penalty
    bbox = block.get("bbox")
    if not bbox or len(bbox) != 4 or bbox == [0, 0, 0, 0]:
        confidence -= 0.15

    return round(max(0.0, min(1.0, confidence)), 4)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _jaccard_bigram_similarity(s1: str, s2: str) -> float:
    """Compute Jaccard similarity based on character bigrams."""
    if not s1 or not s2:
        return 0.0

    def bigrams(s: str) -> set[str]:
        return {s[i:i+2] for i in range(len(s) - 1)}

    b1 = bigrams(s1)
    b2 = bigrams(s2)

    if not b1 and not b2:
        return 1.0
    if not b1 or not b2:
        return 0.0

    intersection = b1 & b2
    union = b1 | b2

    return len(intersection) / len(union)
