"""
Validation layer for legal document OCR extraction.

Cross-checks (accuracy-oriented; VLM 开启时尽量与几何 OCR 对齐):
  - Dual-engine consensus: VLM 全文 vs PaddleOCR 全文（字符 bigram Jaccard）+
    块数量比例，异常时写入 notes 提醒人工复核
  - Per-block confidence: OCR 子串/字级 bigram 重合、法律 group_id、bbox 是否可用
  - Legal field heuristics: 案号、日期、金额等正则扫描，可疑值写入 warnings
  - 关键字段结构化对照: 案号/金额从 VLM 合并文本与 OCR hint 分别抽取，
    多重集对齐后写入 API `legal_field_diffs`（供前端并排展示与块级标红）

说明：最终展示文本仍以 VLM 结构化结果为主；共识层与对照层均不自动改写正文，避免静默篡改案号/金额。
"""

from __future__ import annotations

import logging
import os
import re
from collections import defaultdict

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

_PARTY_ROLE_RE = re.compile(
    r"(原告|被告|上诉人|被上诉人|申请人|被申请人|第三人)[：:\s]*([^\n，。,；;（）()]{1,40})"
)


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


# ---------------------------------------------------------------------------
# OCR vs VLM: 案号 / 金额 结构化对照（不修改正文，仅输出 diff）
# ---------------------------------------------------------------------------


def _normalize_case_number(raw: str) -> str:
    return (
        raw.replace("（", "(")
        .replace("）", ")")
        .replace(" ", "")
        .replace("\u3000", "")
    )


def _extract_case_number_spans(text: str) -> list[str]:
    return [m.group(0) for m in _CASE_NUMBER_RE.finditer(text or "")]


def _extract_amount_spans(text: str) -> list[tuple[str, float]]:
    """(原始片段, 数值元) 按出现顺序；避免 ¥ 与「元」重复匹配重叠。"""
    if not text:
        return []
    spans: list[tuple[int, int, str, float]] = []
    for m in _AMOUNT_YUAN_RE.finditer(text):
        spans.append((m.start(), m.end(), m.group(0), float(m.group(1).replace(",", ""))))
    for m in _AMOUNT_YUAN_DECIMAL_RE.finditer(text):
        s, e = m.start(), m.end()
        if any(max(a, s) < min(b, e) for a, b, _, _ in spans):
            continue
        spans.append((s, e, m.group(0), float(m.group(1).replace(",", ""))))
    spans.sort(key=lambda x: x[0])
    return [(raw, val) for _, _, raw, val in spans]


def _amount_match_key(val: float) -> str:
    return f"{round(val, 2):.2f}"


def _pair_case_number_rows(v_list: list[str], o_list: list[str]) -> list[dict]:
    vb: defaultdict[str, list[str]] = defaultdict(list)
    for r in v_list:
        vb[_normalize_case_number(r)].append(r)
    ob: defaultdict[str, list[str]] = defaultdict(list)
    for r in o_list:
        ob[_normalize_case_number(r)].append(r)
    rows: list[dict] = []
    for k in sorted(set(vb) | set(ob), key=lambda x: (x == "", x)):
        vs = vb.get(k, [])
        os_ = ob.get(k, [])
        n = min(len(vs), len(os_))
        for i in range(n):
            rows.append({"status": "match", "vlm_raw": vs[i], "ocr_raw": os_[i], "normalized": k})
        for j in range(n, len(vs)):
            rows.append({"status": "vlm_only", "vlm_raw": vs[j], "ocr_raw": None, "normalized": k})
        for j in range(n, len(os_)):
            rows.append({"status": "ocr_only", "vlm_raw": None, "ocr_raw": os_[j], "normalized": k})
    return rows


def _pair_amount_rows(
    v_pairs: list[tuple[str, float]],
    o_pairs: list[tuple[str, float]],
) -> list[dict]:
    vb: defaultdict[str, list[tuple[str, float]]] = defaultdict(list)
    for r, v in v_pairs:
        vb[_amount_match_key(v)].append((r, v))
    ob: defaultdict[str, list[tuple[str, float]]] = defaultdict(list)
    for r, v in o_pairs:
        ob[_amount_match_key(v)].append((r, v))
    rows: list[dict] = []
    for k in sorted(set(vb) | set(ob), key=lambda x: (x == "", x)):
        vs = vb.get(k, [])
        os_ = ob.get(k, [])
        n = min(len(vs), len(os_))
        for i in range(n):
            vr, vv = vs[i]
            oraw, _ov = os_[i]
            rows.append({"status": "match", "vlm_raw": vr, "ocr_raw": oraw, "value_yuan": vv})
        for j in range(n, len(vs)):
            vr, vv = vs[j]
            rows.append({"status": "vlm_only", "vlm_raw": vr, "ocr_raw": None, "value_yuan": vv})
        for j in range(n, len(os_)):
            oraw, ov = os_[j]
            rows.append({"status": "ocr_only", "vlm_raw": None, "ocr_raw": oraw, "value_yuan": ov})
    return rows


def compute_legal_field_diffs_for_page(
    vlm_text: str,
    ocr_text: str | None,
    page: int,
) -> dict:
    """单页：从 VLM 全文与 OCR 全文抽取案号、金额并做多重集对齐。"""
    ocr_t = (ocr_text or "").strip()
    vlm_t = vlm_text or ""
    if not ocr_t:
        return {
            "page": page,
            "case_numbers": [],
            "amounts": [],
            "has_discrepancy": False,
            "ocr_unavailable": True,
        }

    case_rows = _pair_case_number_rows(
        _extract_case_number_spans(vlm_t),
        _extract_case_number_spans(ocr_t),
    )
    amt_rows = _pair_amount_rows(
        _extract_amount_spans(vlm_t),
        _extract_amount_spans(ocr_t),
    )

    def _has_mismatch(rows: list[dict]) -> bool:
        return any(r["status"] != "match" for r in rows)

    return {
        "page": page,
        "case_numbers": case_rows,
        "amounts": amt_rows,
        "has_discrepancy": _has_mismatch(case_rows) or _has_mismatch(amt_rows),
        "ocr_unavailable": False,
    }


def merge_legal_field_page_diffs(pages: list[dict]) -> dict | None:
    if not pages:
        return None
    return {
        "has_discrepancy": any(p.get("has_discrepancy") for p in pages),
        "pages": pages,
    }


def extract_evidence_items(
    blocks: list[dict],
    legal_field_diffs: dict | None = None,
) -> list[dict]:
    """Derive lightweight evidence units from extracted blocks.

    This is intentionally heuristic and additive: it does not mutate OCR/VLM
    output, only surfaces high-signal legal facts as reviewable evidence items.
    """
    items: list[dict] = []
    seen: set[tuple] = set()
    mismatch_case_keys: dict[int, set[str]] = defaultdict(set)
    mismatch_amount_keys: dict[int, set[str]] = defaultdict(set)

    for page in (legal_field_diffs or {}).get("pages", []):
        page_no = int(page.get("page") or 1)
        for row in page.get("case_numbers", []):
            if row.get("status") != "match" and row.get("normalized"):
                mismatch_case_keys[page_no].add(row["normalized"])
        for row in page.get("amounts", []):
            if row.get("status") != "match" and row.get("value_yuan") is not None:
                mismatch_amount_keys[page_no].add(_amount_match_key(float(row["value_yuan"])))

    for idx, block in enumerate(blocks):
        text = (block.get("text") or "").strip()
        if not text:
            continue

        page = int(block.get("page") or 1)
        confidence = block.get("confidence")
        bbox = block.get("bbox")
        block_type = block.get("structure_type") or block.get("type") or "text"
        base_missing_fields: list[str] = []
        if confidence is None:
            base_missing_fields.append("confidence")
        if not bbox:
            base_missing_fields.append("bbox")

        for raw in _extract_case_number_spans(text):
            normalized = _normalize_case_number(raw)
            key = ("case_number", page, normalized)
            if key in seen:
                continue
            seen.add(key)
            review_reasons = []
            if normalized in mismatch_case_keys.get(page, set()):
                review_reasons.append("ocr_vlm_case_number_mismatch")
            items.append({
                "id": f"case_number:{page}:{len(items)}",
                "page": page,
                "evidence_type": "case_number",
                "label": "案号",
                "summary": raw,
                "source_text": text,
                "normalized_value": normalized,
                "source_block_index": idx,
                "confidence": confidence,
                "missing_fields": list(base_missing_fields),
                "needs_review": bool(review_reasons or base_missing_fields),
                "review_reasons": review_reasons,
                "parties": [],
                "dates": [],
            })

        for raw, amount in _extract_amount_spans(text):
            amount_key = _amount_match_key(amount)
            key = ("amount", page, amount_key)
            if key in seen:
                continue
            seen.add(key)
            review_reasons = []
            if amount_key in mismatch_amount_keys.get(page, set()):
                review_reasons.append("ocr_vlm_amount_mismatch")
            items.append({
                "id": f"amount:{page}:{len(items)}",
                "page": page,
                "evidence_type": "amount",
                "label": "金额",
                "summary": f"{raw} ({amount:,.2f} 元)",
                "source_text": text,
                "normalized_value": amount_key,
                "amount_yuan": round(amount, 2),
                "source_block_index": idx,
                "confidence": confidence,
                "missing_fields": list(base_missing_fields),
                "needs_review": bool(review_reasons or base_missing_fields),
                "review_reasons": review_reasons,
                "parties": [],
                "dates": [],
            })

        dates = _extract_date_values(text)
        for date_value in dates:
            key = ("date", page, date_value)
            if key in seen:
                continue
            seen.add(key)
            items.append({
                "id": f"date:{page}:{len(items)}",
                "page": page,
                "evidence_type": "date",
                "label": "日期",
                "summary": date_value,
                "source_text": text,
                "normalized_value": date_value,
                "source_block_index": idx,
                "confidence": confidence,
                "missing_fields": list(base_missing_fields),
                "needs_review": bool(base_missing_fields),
                "review_reasons": [],
                "parties": [],
                "dates": [date_value],
            })

        parties = _extract_party_mentions(text)
        if parties:
            normalized_party_key = "|".join(f"{p['role']}:{p['name']}" for p in parties)
            key = ("party", page, normalized_party_key)
            if key in seen:
                continue
            seen.add(key)
            items.append({
                "id": f"party:{page}:{len(items)}",
                "page": page,
                "evidence_type": "party",
                "label": "当事人",
                "summary": "；".join(f"{p['role']}：{p['name']}" for p in parties),
                "source_text": text,
                "normalized_value": normalized_party_key,
                "source_block_index": idx,
                "confidence": confidence,
                "missing_fields": list(base_missing_fields),
                "needs_review": bool(base_missing_fields),
                "review_reasons": [],
                "parties": [f"{p['role']}:{p['name']}" for p in parties],
                "dates": dates,
            })

        if block_type in _LEGAL_GROUP_IDS and len(text) >= 20:
            key = ("fact", page, text[:80])
            if key in seen:
                continue
            seen.add(key)
            items.append({
                "id": f"fact:{page}:{len(items)}",
                "page": page,
                "evidence_type": "fact",
                "label": "事实片段",
                "summary": text[:80] + ("..." if len(text) > 80 else ""),
                "source_text": text,
                "normalized_value": None,
                "source_block_index": idx,
                "confidence": confidence,
                "missing_fields": list(base_missing_fields),
                "needs_review": bool(base_missing_fields),
                "review_reasons": [],
                "parties": [f"{p['role']}:{p['name']}" for p in parties],
                "dates": dates,
            })

    return items


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

    # 略严阈值：法律场景宁可多报警、少漏报（可调低环境变量以放宽）
    _sim_warn = float(os.environ.get("VLM_CONSENSUS_SIM_WARN_BELOW", "0.58"))
    if text_similarity < _sim_warn and combined_ocr.strip():
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
        # 中英混合法律文本：用字级 bigram 与 OCR 全文的局部重合（非「按字符当单词」）
        t = text.strip()
        if len(t) >= 2 and _jaccard_bigram_similarity(t, ocr_text) >= 0.35:
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


def _extract_date_values(text: str) -> list[str]:
    values: list[str] = []
    for m in _DATE_YEAR_MONTH_DAY_RE.finditer(text or ""):
        values.append(f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}")
    for m in _DATE_ISO_RE.finditer(text or ""):
        values.append(f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}")
    return list(dict.fromkeys(values))


def _extract_party_mentions(text: str) -> list[dict]:
    parties: list[dict] = []
    for m in _PARTY_ROLE_RE.finditer(text or ""):
        name = m.group(2).strip()
        if not name:
            continue
        parties.append({
            "role": m.group(1),
            "name": name,
        })
    return parties
