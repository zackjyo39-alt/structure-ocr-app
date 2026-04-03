import React, { useState, useRef, useCallback, useEffect, useMemo } from "react";
import { createRoot } from "react-dom/client";
import { marked } from "marked";

marked.setOptions({ gfm: true, breaks: false });

const API_BASE = "http://localhost:8000";
const SUPPORTED_TYPES = [".pdf", ".png", ".jpg", ".jpeg", ".webp", ".txt"];
const MAX_FILE_SIZE = 50 * 1024 * 1024;

function bboxToRect(bbox) {
  if (!bbox || bbox.length < 4) return null;
  if (bbox.length >= 8) {
    const xs = [bbox[0], bbox[2], bbox[4], bbox[6]];
    const ys = [bbox[1], bbox[3], bbox[5], bbox[7]];
    return {
      minX: Math.min(...xs),
      minY: Math.min(...ys),
      maxX: Math.max(...xs),
      maxY: Math.max(...ys),
    };
  }
  return { minX: bbox[0], minY: bbox[1], maxX: bbox[2], maxY: bbox[3] };
}

function pointInRect(x, y, r) {
  return x >= r.minX && x <= r.maxX && y >= r.minY && y <= r.maxY;
}

function computeBlockSpans(text, blocks) {
  if (!text || !blocks?.length) return blocks.map(() => ({ start: null, end: null }));
  let pos = 0;
  return blocks.map((block) => {
    const chunk = block.text ?? "";
    if (!chunk) return { start: null, end: null };
    let idx = text.indexOf(chunk, pos);
    if (idx === -1) idx = text.indexOf(chunk);
    if (idx === -1) return { start: null, end: null };
    const span = { start: idx, end: idx + chunk.length };
    pos = idx + chunk.length;
    return span;
  });
}

function lineColAtOffset(text, offset) {
  if (offset == null || offset < 0 || !text) return { line: null, col: null };
  const head = text.slice(0, offset);
  const lines = head.split("\n");
  const line = lines.length;
  const col = (lines[lines.length - 1] ?? "").length + 1;
  return { line, col };
}

/** Layout 块是否与「案号/金额 OCR↔VLM 不一致」片段相交（用于标红提示） */
function blockTouchesLegalDiff(block, diffs) {
  if (!diffs?.pages?.length || !block?.text) return false;
  const t = block.text;
  for (const p of diffs.pages) {
    for (const row of [...(p.case_numbers || []), ...(p.amounts || [])]) {
      if (row.status === "match") continue;
      if (row.vlm_raw && t.includes(row.vlm_raw)) return true;
      if (row.ocr_raw && t.includes(row.ocr_raw)) return true;
    }
  }
  return false;
}

// ---------------------------------------------------------------------------
// Cross-validation helpers
// ---------------------------------------------------------------------------

function cvStatusMeta(status) {
  return {
    match:          { label: "双引擎一致",   color: "#34d399", bg: "rgba(52,211,153,0.12)" },
    mismatch:       { label: "不一致·需复核", color: "#f87171", bg: "rgba(248,113,113,0.14)" },
    primary_only:   { label: "仅主引擎",     color: "#fbbf24", bg: "rgba(251,191,36,0.12)" },
    secondary_only: { label: "仅副引擎",     color: "#a78bfa", bg: "rgba(167,139,250,0.12)" },
  }[status] || { label: status, color: "#9ca3af", bg: "transparent" };
}

function CrossValidationSummaryPanel({ summary }) {
  if (!summary) return null;

  const { primary_engine, secondary_engine, total_blocks, matched, mismatched,
          primary_only, secondary_only, agreement_rate, mismatches } = summary;
  const isGreen = agreement_rate >= 0.95;
  const isYellow = !isGreen && agreement_rate >= 0.80;

  const borderColor = isGreen ? "rgba(52,211,153,0.5)"
                    : isYellow ? "rgba(251,191,36,0.5)"
                    : "rgba(248,113,113,0.5)";
  const bgColor = isGreen ? "rgba(52,211,153,0.06)"
                : isYellow ? "rgba(251,191,36,0.06)"
                : "rgba(248,113,113,0.06)";
  const rateColor = isGreen ? "#34d399" : isYellow ? "#fbbf24" : "#f87171";

  return (
    <div style={{ marginBottom: 12, borderRadius: 8, border: `1px solid ${borderColor}`, background: bgColor, padding: "12px 14px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: "#e6edf3" }}>
          🔄 双引擎交叉验证报告
        </span>
        <span style={{ fontSize: 12, color: "#6b7280" }}>
          {primary_engine} × {secondary_engine}
        </span>
        <span style={{ marginLeft: "auto", fontSize: 13, fontWeight: 700, color: rateColor }}>
          一致率 {(agreement_rate * 100).toFixed(1)}%
        </span>
      </div>

      {/* Stats grid */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 10 }}>
        {[
          { label: "总块数", value: total_blocks, color: "#9ca3af" },
          { label: "一致",   value: matched,      color: "#34d399" },
          { label: "不一致", value: mismatched,    color: "#f87171" },
          { label: "仅主引擎", value: primary_only, color: "#fbbf24" },
          { label: "仅副引擎", value: secondary_only, color: "#a78bfa" },
        ].map(({ label, value, color }) => (
          <div key={label} style={{
            background: "#1c2128", borderRadius: 6, padding: "4px 10px",
            fontSize: 12, color: "#9ca3af", border: "1px solid #30363d",
          }}>
            <span style={{ color }}>{value}</span> {label}
          </div>
        ))}
      </div>

      {/* Mismatch detail table */}
      {mismatches?.length > 0 && (
        <div>
          <div style={{ fontSize: 11, color: "#8b949e", marginBottom: 6, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>
            不一致明细（需人工复核）
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "36px minmax(0,1fr) minmax(0,1fr) 52px", gap: 4, fontSize: 11, color: "#6b7280", marginBottom: 4 }}>
            <span>页</span><span>主引擎文本</span><span>副引擎文本</span><span>相似度</span>
          </div>
          {mismatches.slice(0, 8).map((m, i) => (
            <div key={i} style={{
              display: "grid", gridTemplateColumns: "36px minmax(0,1fr) minmax(0,1fr) 52px",
              gap: 4, padding: "5px 0", borderTop: "1px solid #21262d",
              alignItems: "start", fontSize: 12,
            }}>
              <span style={{ color: "#6b7280" }}>{m.page}</span>
              <span style={{ color: "#f87171", wordBreak: "break-all" }}>{m.primary_text || "—"}</span>
              <span style={{ color: "#fbbf24", wordBreak: "break-all" }}>{m.secondary_text || "—"}</span>
              <span style={{ color: "#9ca3af" }}>{((m.similarity ?? 0) * 100).toFixed(0)}%</span>
            </div>
          ))}
          {mismatches.length > 8 && (
            <div style={{ fontSize: 11, color: "#6b7280", paddingTop: 4 }}>
              …还有 {mismatches.length - 8} 处不一致
            </div>
          )}
        </div>
      )}
      <div style={{ fontSize: 11, color: "#4b5563", marginTop: 8, lineHeight: 1.5 }}>
        算法：逐块 IoU 区域对齐 + 字符 bigram Jaccard 文本相似度；阈值 IoU≥0.35 / 文本≥0.80 判为一致。
      </div>
    </div>
  );
}

function statusLabelLegalDiff(status) {
  const m = { match: "一致", vlm_only: "仅 VLM", ocr_only: "仅 OCR" };
  return m[status] || status;
}

function LegalFieldDiffPanel({ diffs }) {
  if (!diffs?.pages?.length) return null;

  const rows = [];
  for (const p of diffs.pages) {
    const pn = p.page;
    if (p.ocr_unavailable) {
      rows.push({
        key: `p${pn}-skip`,
        page: pn,
        kind: "meta",
        text: "本页无 OCR 全文对照（未生成 OCR hint，请确认 OCR 引擎已安装：pip install -e '.[auto]'）",
      });
      continue;
    }
    const cn = p.case_numbers || [];
    const am = p.amounts || [];
    if (!cn.length && !am.length) continue;
    for (const r of cn) {
      rows.push({ key: `p${pn}-c-${rows.length}`, page: pn, kind: "案号", ...r });
    }
    for (const r of am) {
      rows.push({ key: `p${pn}-a-${rows.length}`, page: pn, kind: "金额", ...r });
    }
  }

  if (!rows.length) return null;

  const anyBad = !!diffs.has_discrepancy;

  const cell = (val, hot) => (
    <span style={{
      color: hot ? "#f87171" : "#e6edf3",
      background: hot ? "rgba(248,113,113,0.14)" : "transparent",
      padding: "2px 4px",
      borderRadius: 4,
      wordBreak: "break-all",
    }}>{val || "—"}</span>
  );

  return (
    <div style={{
      marginBottom: 12,
      borderRadius: 8,
      border: anyBad ? "1px solid rgba(248,113,113,0.45)" : "1px solid rgba(52,211,153,0.35)",
      background: anyBad ? "rgba(248,113,113,0.06)" : "rgba(52,211,153,0.06)",
      padding: "12px 14px",
    }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: "#e6edf3", marginBottom: 8 }}>
        关键字段 OCR / VLM 对照
        {anyBad ? (
          <span style={{ marginLeft: 8, color: "#f87171", fontWeight: 500 }}>存在不一致，请人工复核</span>
        ) : (
          <span style={{ marginLeft: 8, color: "#34d399", fontWeight: 500 }}>已抽取项成对一致</span>
        )}
      </div>
      <div style={{ fontSize: 11, color: "#6b7280", marginBottom: 10, lineHeight: 1.5 }}>
        正则从 VLM 合并文本与 OCR hint 抽取；案号在比对前归一全半角括号；金额按数值（分到分）对齐。
      </div>
      <div style={{
        display: "grid",
        gridTemplateColumns: "44px 44px minmax(0,1fr) minmax(0,1fr) 64px",
        gap: 6,
        fontSize: 12,
        color: "#9ca3af",
        marginBottom: 4,
      }}>
        <span>页</span>
        <span>类</span>
        <span>VLM</span>
        <span>OCR</span>
        <span>状态</span>
      </div>
      {rows.map((row) => {
        if (row.kind === "meta") {
          return (
            <div key={row.key} style={{ fontSize: 12, color: "#8b949e", marginBottom: 8 }}>
              第 {row.page} 页 · {row.text}
            </div>
          );
        }
        const st = row.status;
        const isOk = st === "match";
        return (
          <div
            key={row.key}
            style={{
              display: "grid",
              gridTemplateColumns: "44px 44px minmax(0,1fr) minmax(0,1fr) 64px",
              gap: 6,
              alignItems: "start",
              padding: "6px 0",
              borderTop: "1px solid #30363d",
              fontSize: 12,
            }}
          >
            <span style={{ color: "#8b949e" }}>{row.page}</span>
            <span style={{ color: "#a78bfa" }}>{row.kind}</span>
            <div>{cell(row.vlm_raw, st === "vlm_only")}</div>
            <div>{cell(row.ocr_raw, st === "ocr_only")}</div>
            <span style={{ color: isOk ? "#34d399" : "#fbbf24" }}>{statusLabelLegalDiff(st)}</span>
          </div>
        );
      })}
    </div>
  );
}

function offsetFromPointInTextElement(el, clientX, clientY) {
  if (!el) return null;
  let range = null;
  if (document.caretRangeFromPoint) {
    range = document.caretRangeFromPoint(clientX, clientY);
  } else if (document.caretPositionFromPoint) {
    const pos = document.caretPositionFromPoint(clientX, clientY);
    if (pos?.offsetNode) {
      range = document.createRange();
      range.setStart(pos.offsetNode, pos.offset);
      range.setEnd(pos.offsetNode, pos.offset);
    }
  }
  if (!range || !el.contains(range.startContainer)) return null;
  if (range.startContainer.nodeType !== Node.TEXT_NODE) return null;
  let off = 0;
  const walk = (node) => {
    if (node === range.startContainer) {
      off += range.startOffset;
      return true;
    }
    if (node.nodeType === Node.TEXT_NODE) {
      off += node.textContent.length;
      return false;
    }
    for (const c of node.childNodes) {
      if (walk(c)) return true;
    }
    return false;
  };
  walk(el);
  return off;
}

const STRUCTURE_COLORS = {
  title: "#3b82f6",
  caption: "#8b5cf6",
  text: "#6366f1",
  table: "#f59e0b",
  figure: "#22c55e",
  header: "#6b7280",
  footer: "#6b7280",
  equation: "#ec4899",
  footnote: "#9ca3af",
  list: "#14b8a6",
};

function getStructureColor(block) {
  const st = block.structure_type || block.type;
  return STRUCTURE_COLORS[st] || STRUCTURE_COLORS.text;
}

function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

function computeFontSize(bbox, hierarchyLevel) {
  if (bbox && bbox.length >= 4) {
    const height = bbox[3] - bbox[1];
    const base = Math.max(10, Math.min(height * 0.65, 36));
    if (hierarchyLevel != null && hierarchyLevel <= 1) return Math.min(base * 1.4, 36);
    if (hierarchyLevel != null && hierarchyLevel === 2) return Math.min(base * 1.2, 28);
    return base;
  }
  const sizeMap = { 0: 28, 1: 22, 2: 18, 3: 16, 4: 13, 5: 12, 6: 11 };
  return sizeMap[hierarchyLevel] || 13;
}

function StructureView({ blocks, pageInfos, highlightedBlockIndex, setHighlightedBlockIndex }) {
  const canvasRef = useRef(null);
  const [canvasSize, setCanvasSize] = useState({ w: 0, h: 0 });
  const [scale, setScale] = useState(1);

  const pageInfo = pageInfos?.[0] || null;
  const pageW = pageInfo?.width || 1200;
  const pageH = pageInfo?.height || 1600;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setCanvasSize({ w: entry.contentRect.width, h: entry.contentRect.height });
      }
    });
    ro.observe(canvas);
    return () => ro.disconnect();
  }, []);

  const getPageScale = (pageW) => {
    if (canvasSize.w > 0 && pageW > 0) {
      return canvasSize.w / pageW;
    }
    return 1;
  };

  const blocksWithBbox = blocks.filter(b => b.bbox && b.bbox.length >= 4);
  const blocksWithoutBbox = blocks.filter(b => !b.bbox || b.bbox.length < 4);

  if (!blocks.length) {
    return (
      <div style={{ color: "#8b949e", textAlign: "center", padding: 40 }}>
        No structure data available for reconstruction
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <style>{`
        .markdown-content h1, .markdown-content h2, .markdown-content h3,
        .markdown-content h4, .markdown-content h5, .markdown-content h6 {
          margin: 0 0 4px 0;
          font-weight: 700;
          line-height: 1.2;
        }
        .markdown-content h1 { font-size: 1.4em; }
        .markdown-content h2 { font-size: 1.2em; }
        .markdown-content h3 { font-size: 1.1em; }
        .markdown-content p { margin: 0 0 4px 0; }
        .markdown-content ul, .markdown-content ol {
          margin: 0;
          padding-left: 16px;
          list-style-position: inside;
        }
        .markdown-content li { margin: 2px 0; }
        .markdown-content code {
          background: #f0f0f0;
          padding: 1px 3px;
          border-radius: 2px;
          font-family: ui-monospace, monospace;
          font-size: 0.9em;
        }
        .markdown-content pre {
          background: #f5f5f5;
          padding: 6px;
          border-radius: 3px;
          overflow: auto;
          font-size: 0.85em;
        }
        .markdown-content pre code {
          background: transparent;
          padding: 0;
        }
        .markdown-content blockquote {
          margin: 4px 0;
          padding-left: 8px;
          border-left: 3px solid #ddd;
          color: #555;
        }
        .markdown-content table {
          width: 100%;
          border-collapse: collapse;
          margin: 4px 0;
          font-size: 0.9em;
        }
        .markdown-content th, .markdown-content td {
          border: 1px solid #ccc;
          padding: 2px 4px;
        }
        .markdown-content th {
          background: #e8e8e8;
          font-weight: 600;
        }
        .markdown-content hr {
          margin: 4px 0;
          border: none;
          border-top: 1px solid #ddd;
        }
        .markdown-content a {
          color: #6366f1;
          text-decoration: underline;
        }
        .markdown-content strong { font-weight: 700; }
        .markdown-content em { font-style: italic; }
      `}</style>
      <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "#6b7280" }}>
        <span>Pixel-level reconstruction</span>
        <span>·</span>
        <span>{blocksWithBbox.length} positioned blocks</span>
        {blocksWithoutBbox.length > 0 && (
          <>
            <span>·</span>
            <span>{blocksWithoutBbox.length} without coordinates</span>
          </>
        )}
      </div>
      <div
        ref={canvasRef}
        style={{
          width: "100%",
          display: "flex",
          flexDirection: "column",
          gap: 24,
        }}
      >
        {(pageInfos || []).map((page, pIdx) => {
          const pageBlocks = blocksWithBbox.filter(b => b.page === page.page);
          const pW = page.width || 1200;
          const pH = page.height || 1600;
          const pScale = getPageScale(pW);

          return (
            <div
              key={pIdx}
              style={{
                position: "relative",
                width: "100%",
                height: pH * pScale,
                background: "#ffffff",
                borderRadius: 4,
                overflow: "hidden",
                boxShadow: "0 0 10px rgba(0,0,0,0.2)",
              }}
            >
              <div
                style={{
                  position: "relative",
                  width: pW,
                  height: pH,
                  transform: `scale(${pScale})`,
                  transformOrigin: "top left",
                }}
              >
                {page.image_data && (
                  <img
                    src={page.image_data}
                    alt={`Page ${page.page}`}
                    style={{ position: "absolute", left: 0, top: 0, width: pW, height: pH }}
                  />
                )}
                {pageBlocks.map((block, idx) => {
                  const globalIdx = blocks.indexOf(block);
                  const isHighlighted = highlightedBlockIndex === globalIdx;
                  const r = bboxToRect(block.bbox);
                  if (!r) return null;
                  const left = r.minX;
                  const top = r.minY;
                  const w = r.maxX - r.minX;
                  const h = r.maxY - r.minY;
                  const fontSize = computeFontSize(block.bbox, block.hierarchy_level);
                  const color = getStructureColor(block);

                  if (block.table_html) {
                    return (
                      <div key={idx} style={{ position: "absolute", left, top, width: w, height: h, overflow: "hidden" }}>
                        <div
                          className="structure-table"
                          style={{ background: "transparent" }}
                          dangerouslySetInnerHTML={{ __html: block.table_html }}
                        />
                        <style>{`
                          .structure-table table { width: 100%; border-collapse: collapse; font-size: ${Math.max(9, fontSize * 0.8)}px; }
                          .structure-table th, .structure-table td { border: 1px solid #ccc; padding: 2px 4px; color: #1a1a1a; }
                          .structure-table th { background: #e8e8e8; font-weight: 600; }
                        `}</style>
                      </div>
                    );
                  }

                  return (
                    <div
                      key={idx}
                      onMouseEnter={() => setHighlightedBlockIndex(globalIdx)}
                      onMouseLeave={() => setHighlightedBlockIndex(null)}
                      style={{
                        position: "absolute",
                        left,
                        top,
                        width: w,
                        minHeight: h,
                        padding: "1px 2px",
                        background: isHighlighted ? hexToRgba(color, 0.15) : "transparent",
                        border: isHighlighted ? `1px solid ${color}` : "1px solid transparent",
                        borderRadius: 1,
                        transition: "background 0.1s, border-color 0.1s",
                        cursor: "text",
                        overflow: "hidden",
                        color: "transparent",
                      }}
                    >
                      <div
                        className="markdown-content"
                        style={{
                          fontSize,
                          lineHeight: 1.3,
                          color: isHighlighted ? "#1a1a1a" : "transparent",
                          fontFamily: block.structure_type === "equation" ? "Georgia, serif" : "inherit",
                          fontWeight: (block.hierarchy_level != null && block.hierarchy_level <= 1) ? 700 : (block.hierarchy_level === 2 ? 600 : 400),
                          wordBreak: "break-word",
                          userSelect: "text",
                        }}
                        dangerouslySetInnerHTML={{ __html: marked.parse(block.text || "") }}
                      />
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
      {blocksWithoutBbox.length > 0 && (
        <div style={{ background: "#1c2128", borderRadius: 8, padding: 12 }}>
          <div style={{ fontSize: 12, color: "#8b949e", marginBottom: 8 }}>
            Blocks without coordinates ({blocksWithoutBbox.length})
          </div>
          {blocksWithoutBbox.slice(0, 10).map((block, i) => (
            <div key={i} style={{ fontSize: 12, color: "#6b7280", marginBottom: 4, paddingLeft: (block.hierarchy_level || 0) * 8 }}>
              <span style={{ color: getStructureColor(block), marginRight: 6 }}>●</span>
              {block.text?.slice(0, 80)}{block.text?.length > 80 ? "..." : ""}
            </div>
          ))}
          {blocksWithoutBbox.length > 10 && (
            <div style={{ fontSize: 11, color: "#4b5563" }}>... and {blocksWithoutBbox.length - 10} more</div>
          )}
        </div>
      )}
    </div>
  );
}

function Sidebar({ activeView, setActiveView, onNewExtraction }) {
  const items = [
    { id: "workspace", label: "Extraction", icon: "✦" },
    { id: "config", label: "VLM Config", icon: "⚙" },
    { id: "history", label: "History", icon: "◷" },
    { id: "help", label: "Help", icon: "?" },
  ];
  return (
    <aside style={{
      width: 200, background: "#161b22", borderRight: "1px solid #30363d",
      display: "flex", flexDirection: "column", padding: "16px 0"
    }}>
      <div style={{ padding: "0 16px 20px", borderBottom: "1px solid #30363d", marginBottom: 12 }}>
        <h1 style={{ fontSize: 16, fontWeight: 700, color: "#e6edf3" }}>Structure-OCR</h1>
        <span style={{ fontSize: 11, color: "#8b949e", display: "block", marginTop: 2 }}>Phase 1 Demo</span>
      </div>
      <nav>
        {items.map(item => (
          <button key={item.id} onClick={() => setActiveView(item.id)} style={{
            background: activeView === item.id ? "#262c36" : "transparent",
            color: activeView === item.id ? "#e6edf3" : "#8b949e", border: "none",
            padding: "10px 16px", cursor: "pointer", textAlign: "left",
            fontSize: 13, display: "flex", alignItems: "center", gap: 10, width: "100%"
          }}>
            <span>{item.icon}</span> {item.label}
          </button>
        ))}
      </nav>
    </aside>
  );
}

function Header({ activeView }) {
  return (
    <header style={{
      height: 48, background: "#161b22", borderBottom: "1px solid #30363d",
      display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 24px"
    }}>
      <span style={{ fontSize: 13, color: "#8b949e", textTransform: "capitalize" }}>
        {activeView === "workspace" ? "Extraction Workspace" : activeView === "config" ? "VLM Config" : activeView}
      </span>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ width: 30, height: 30, borderRadius: "50%", background: "#6366f1", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 600, color: "#fff" }}>U</div>
      </div>
    </header>
  );
}

function ConfigPanel({ vlmConfig, setVlmConfig }) {
  const [form, setForm] = useState({
    enabled: false,
    provider: "ollama",
    model: "",
    base_url: "",
    api_key: "",
  });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [ollamaStatus, setOllamaStatus] = useState(null); // null | "checking" | "running" | "stopped"
  const [ollamaModels, setOllamaModels] = useState([]);
  const [testStatus, setTestStatus] = useState(null); // null | "testing" | { status: "ok"|"error"|"warning", message?: string, error?: string }

  const checkOllama = useCallback(async (baseUrl) => {
    setOllamaStatus("checking");
    try {
      const url = `${API_BASE}/api/health/ollama?base_url=${encodeURIComponent(baseUrl || "http://localhost:11434/api/chat")}`;
      const res = await fetch(url);
      const data = await res.json();
      setOllamaStatus(data.running ? "running" : "stopped");
      setOllamaModels(data.models || []);
    } catch {
      setOllamaStatus("stopped");
      setOllamaModels([]);
    }
  }, []);

  // Auto-check Ollama when provider is ollama
  useEffect(() => {
    if (form.provider === "ollama") {
      checkOllama(form.base_url);
    } else {
      setOllamaStatus(null);
    }
  }, [form.provider, checkOllama]);

  const presets = useMemo(() => vlmConfig?.presets || {}, [vlmConfig]);
  const presetEntries = useMemo(() => Object.entries(presets), [presets]);

  const defaultGeminiBase = "https://generativelanguage.googleapis.com/v1beta";

  useEffect(() => {
    if (!vlmConfig) return;
    const prov = (vlmConfig.provider || "ollama").toLowerCase();
    const bu = (vlmConfig.base_url || "").trim();
    setForm({
      enabled: !!vlmConfig.enabled,
      provider: vlmConfig.provider || "ollama",
      model: vlmConfig.model || "",
      base_url: prov === "gemini" && !bu ? defaultGeminiBase : vlmConfig.base_url || "",
      api_key: vlmConfig.api_key || "",
    });
  }, [vlmConfig]);

  const loadConfig = useCallback(async () => {
    setLoading(true);
    setError("");
    setStatus("");
    try {
      const res = await fetch(`${API_BASE}/api/vlm-config`);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      }
      const data = await res.json();
      setVlmConfig(data);
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      setLoading(false);
    }
  }, [setVlmConfig]);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  const updateField = (key, value) => {
    setForm((current) => ({ ...current, [key]: value }));
    setStatus("");
  };

  const handlePresetChange = (presetId) => {
    if (!presetId) return;
    if (presetId === "__local_deepseek__") {
      setForm((current) => ({
        ...current,
        provider: "ollama",
        model: "deepseek-ocr:3b",
        base_url: "http://localhost:11434/api/chat",
      }));
      setStatus("已载入预设：Ollama · deepseek-ocr:3b");
      return;
    }
    const preset = presets[presetId];
    if (!preset) return;
    setForm((current) => ({
      ...current,
      provider: preset.provider || current.provider,
      model: preset.model || "",
      base_url: preset.base_url || "",
      api_key: preset.api_key || current.api_key,
    }));
    setStatus(`已载入预设：${preset.label}`);
  };

  const handleSave = async () => {
    setSaving(true);
    setError("");
    setStatus("");
    try {
      const payload = {
        enabled: !!form.enabled,
        provider: form.provider.trim(),
        model: form.model.trim(),
        base_url: form.base_url.trim(),
        api_key: form.api_key,
      };
      const res = await fetch(`${API_BASE}/api/vlm-config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      }
      const data = await res.json();
      setVlmConfig({ ...vlmConfig, ...data, presets });
      setStatus("配置已保存，下一次抽取会直接使用最新 VLM 配置。");
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTestStatus("testing");
    setStatus("");
    setError("");
    try {
      const payload = {
        provider: form.provider.trim(),
        model: form.model.trim(),
        base_url: form.base_url.trim(),
        api_key: form.api_key,
      };
      const res = await fetch(`${API_BASE}/api/vlm-test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      }
      const data = await res.json();
      setTestStatus(data);
    } catch (err) {
      setTestStatus({ status: "error", error: err.message || String(err) });
    }
  };

  const cardStyle = {
    background: "#161b22",
    border: "1px solid #30363d",
    borderRadius: 12,
    padding: 20,
  };

  return (
    <div style={{ flex: 1, overflow: "auto", padding: 24, background: "#0d1117" }}>
      <div style={{ maxWidth: 920, margin: "0 auto", display: "flex", flexDirection: "column", gap: 16 }}>
        <div>
          <div style={{ fontSize: 28, fontWeight: 700, color: "#e6edf3", marginBottom: 8 }}>Backend Config</div>
          <div style={{ fontSize: 14, color: "#8b949e", lineHeight: 1.6 }}>
            这里可以切换结构化 OCR 的底层引擎。保存后无需重启后端，下一次调用 `/api/extract` 会直接采用最新配置。
          </div>
        </div>

        <div style={cardStyle}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "flex-start", flexWrap: "wrap" }}>
            <div>
              <div style={{ fontSize: 16, color: "#e6edf3", fontWeight: 600, marginBottom: 6 }}>VLM 模式</div>
              <div style={{ fontSize: 13, color: "#8b949e", maxWidth: 560 }}>
                关闭时走几何 OCR 路线（引擎由后端环境变量决定）；开启后，后端会优先使用你当前保存的多模态模型配置。
              </div>
            </div>
            <label style={{ display: "flex", alignItems: "center", gap: 10, color: "#e6edf3", fontSize: 14 }}>
              <input
                type="checkbox"
                checked={!!form.enabled}
                onChange={(e) => updateField("enabled", e.target.checked)}
                style={{ width: 18, height: 18 }}
              />
              启用 VLM
            </label>
          </div>
        </div>

        <div style={cardStyle}>
          <div style={{ fontSize: 16, color: "#e6edf3", fontWeight: 600, marginBottom: 6 }}>模型预设</div>
          <div style={{ fontSize: 13, color: "#8b949e", marginBottom: 14 }}>
            可以先选预设，再按需继续编辑 Provider、Model、Base URL 和 API Key。
          </div>
          <select
            defaultValue=""
            onChange={(e) => handlePresetChange(e.target.value)}
            style={{
              width: "100%",
              background: "#0d1117",
              color: "#e6edf3",
              border: "1px solid #30363d",
              borderRadius: 8,
              padding: "12px 14px",
              fontSize: 14,
            }}
          >
            <option value="" disabled>选择一个推荐预设</option>
            {presetEntries.map(([id, preset]) => {
              let label = preset.label;
              if (id === "nim-paddleocr-vl") label += " · 推荐：轻量化实时应用";
              if (id === "nim-deepseek-ocr") label += " · 推荐：高质量知识库 RAG 压缩";
              if (id === "ollama-deepseek-ocr") label += " · 推荐：完全本地隐私方案";
              return (
                <option key={id} value={id}>{label}</option>
              );
            })}
            {!presets["ollama-deepseek-ocr"] && (
              <option value="__local_deepseek__">Ollama · deepseek-ocr:3b · 推荐：完全本地隐私方案</option>
            )}
          </select>
          {!presets["ollama-deepseek-ocr"] && (
            <button
              onClick={() => setForm((current) => ({
                ...current,
                provider: "ollama",
                model: "deepseek-ocr:3b",
                base_url: "http://localhost:11434/api/chat",
              }))}
              style={{
                marginTop: 12,
                background: "transparent",
                color: "#7dd3fc",
                border: "1px solid #164e63",
                borderRadius: 8,
                padding: "8px 12px",
                cursor: "pointer",
                fontSize: 13,
              }}
            >
              一键填入 Ollama · deepseek-ocr:3b
            </button>
          )}
        </div>

        <div style={cardStyle}>
          <div style={{ fontSize: 16, color: "#e6edf3", fontWeight: 600, marginBottom: 14 }}>连接参数</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 14 }}>
            <label style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <span style={{ fontSize: 12, color: "#8b949e" }}>Provider</span>
              <input
                value={form.provider}
                onChange={(e) => updateField("provider", e.target.value)}
                placeholder="ollama / openai / gemini"
                style={{
                  background: "#0d1117",
                  color: "#e6edf3",
                  border: "1px solid #30363d",
                  borderRadius: 8,
                  padding: "12px 14px",
                  fontSize: 14,
                }}
              />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <span style={{ fontSize: 12, color: "#8b949e" }}>
                Base URL
                {form.provider === "gemini" && (
                  <span style={{ marginLeft: 8, color: "#a78bfa", fontSize: 11 }}>● API 根路径，可改 v1 / v1beta</span>
                )}
              </span>
              <input
                value={form.base_url}
                onChange={(e) => updateField("base_url", e.target.value)}
                placeholder={
                  form.provider === "gemini"
                    ? "https://generativelanguage.googleapis.com/v1beta（或 …/v1）"
                    : "http://localhost:11434/api/chat"
                }
                style={{
                  background: "#0d1117",
                  color: "#e6edf3",
                  border: "1px solid #30363d",
                  borderRadius: 8,
                  padding: "12px 14px",
                  fontSize: 14,
                }}
              />
              {form.provider === "gemini" && (
                <span style={{ fontSize: 11, color: "#6b7280", lineHeight: 1.4 }}>
                  仅填写到 <code style={{ color: "#8b949e" }}>/v1beta</code> 或 <code style={{ color: "#8b949e" }}>/v1</code>；后端会拼接{" "}
                  <code style={{ color: "#8b949e" }}>/models/&lt;model&gt;:generateContent</code>。
                  若误贴了完整路径，保存时会自动截断到 API 根。模型名须与 Google 文档一致（例如 Gemini 3 Flash 为{" "}
                  <code style={{ color: "#8b949e" }}>gemini-3-flash-preview</code>）。
                </span>
              )}
            </label>
            {/* Model field: dropdown from Ollama when available, else free text */}
            <label style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <span style={{ fontSize: 12, color: "#8b949e" }}>
                Model
                {form.provider === "ollama" && ollamaStatus === "running" && ollamaModels.length > 0 && (
                  <span style={{ marginLeft: 8, color: "#34d399", fontSize: 11 }}>● {ollamaModels.length} 个可用模型</span>
                )}
              </span>
              {form.provider === "ollama" && ollamaStatus === "running" && ollamaModels.length > 0 ? (
                <select
                  value={form.model}
                  onChange={(e) => updateField("model", e.target.value)}
                  style={{
                    background: "#0d1117", color: "#e6edf3",
                    border: "1px solid #34d399", borderRadius: 8,
                    padding: "12px 14px", fontSize: 14,
                  }}
                >
                  <option value="">-- 选择已安装的模型 --</option>
                  {ollamaModels.map(m => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              ) : (
                <input
                  value={form.model}
                  onChange={(e) => updateField("model", e.target.value)}
                  placeholder={
                    form.provider === "ollama" ? "llava / llama3.2-vision (需先 ollama pull)"
                    : form.provider === "gemini" ? "gemini-2.5-flash 或 gemini-3-flash-preview"
                    : form.provider === "openai" ? "gpt-4o-mini"
                    : "meta/llama-3.2-11b-vision-instruct"
                  }
                  style={{
                    background: "#0d1117", color: "#e6edf3",
                    border: "1px solid #30363d", borderRadius: 8,
                    padding: "12px 14px", fontSize: 14,
                  }}
                />
              )}
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: 8, gridColumn: "1 / -1" }}>
              <span style={{ fontSize: 12, color: "#8b949e" }}>API Key</span>
              <input
                type="password"
                value={form.api_key}
                onChange={(e) => updateField("api_key", e.target.value)}
                placeholder="填写 NVIDIA / OpenAI / Gemini 等提供商密钥"
                style={{
                  background: "#0d1117",
                  color: "#e6edf3",
                  border: "1px solid #30363d",
                  borderRadius: 8,
                  padding: "12px 14px",
                  fontSize: 14,
                }}
              />
            </label>
          </div>
        </div>

        <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <button
            onClick={handleTest}
            disabled={testStatus === "testing" || saving || loading}
            style={{
              padding: "12px 18px",
              background: testStatus?.status === "ok" ? "rgba(52,211,153,0.15)" : testStatus?.status === "error" ? "rgba(248,113,113,0.15)" : "#10b981",
              color: testStatus?.status === "ok" ? "#34d399" : testStatus?.status === "error" ? "#f87171" : "#fff",
              border: testStatus?.status ? `1px solid ${testStatus.status === "ok" ? "rgba(52,211,153,0.4)" : "rgba(248,113,113,0.4)"}` : "none",
              borderRadius: 8,
              cursor: testStatus === "testing" || saving || loading ? "not-allowed" : "pointer",
              fontSize: 14,
              fontWeight: 600,
            }}
          >
            {testStatus === "testing" ? "测试中..." : testStatus?.status === "ok" ? "✓ 可用" : testStatus?.status === "error" ? "✗ 不可用" : "测试连接"}
          </button>
          <button
            onClick={handleSave}
            disabled={saving || loading}
            style={{
              padding: "12px 18px",
              background: "#6366f1",
              color: "#fff",
              border: "none",
              borderRadius: 8,
              cursor: saving || loading ? "not-allowed" : "pointer",
              fontSize: 14,
              fontWeight: 600,
            }}
          >
            {saving ? "保存中..." : "保存配置"}
          </button>
          <button
            onClick={loadConfig}
            disabled={saving || loading}
            style={{
              padding: "12px 18px",
              background: "transparent",
              color: "#8b949e",
              border: "1px solid #30363d",
              borderRadius: 8,
              cursor: saving || loading ? "not-allowed" : "pointer",
              fontSize: 14,
            }}
          >
            {loading ? "刷新中..." : "从后端重新读取"}
          </button>
          {status && <span style={{ fontSize: 13, color: "#34d399" }}>{status}</span>}
          {error && <span style={{ fontSize: 13, color: "#f87171" }}>{error}</span>}
        </div>

        {testStatus && testStatus !== "testing" && (
          <div style={{
            background: testStatus.status === "ok" ? "rgba(52,211,153,0.08)" : testStatus.status === "warning" ? "rgba(251,191,36,0.08)" : "rgba(248,113,113,0.08)",
            border: `1px solid ${testStatus.status === "ok" ? "rgba(52,211,153,0.25)" : testStatus.status === "warning" ? "rgba(251,191,36,0.25)" : "rgba(248,113,113,0.25)"}`,
            borderRadius: 8,
            padding: "12px 16px",
            fontSize: 13,
            lineHeight: 1.6,
            color: testStatus.status === "ok" ? "#34d399" : testStatus.status === "warning" ? "#fbbf24" : "#f87171",
          }}>
            {testStatus.message || testStatus.error || "未知状态"}
          </div>
        )}
      </div>
    </div>
  );
}

function BboxOverlay({ blocks, naturalW, naturalH, highlightedBlockIndex, displayW, displayH, pageNum }) {
  if (!naturalW || !naturalH || !displayW || !displayH) return null;
  const sx = displayW / naturalW;
  const sy = displayH / naturalH;
  return (
    <div style={{
      position: "absolute", left: 0, top: 0, width: displayW, height: displayH,
      pointerEvents: "none",
    }}>
      {blocks.map((block, globalIdx) => {
        if (pageNum != null && block.page !== pageNum) return null;
        const r = bboxToRect(block.bbox);
        if (!r) return null;
        const left = r.minX * sx;
        const top = r.minY * sy;
        const w = (r.maxX - r.minX) * sx;
        const h = (r.maxY - r.minY) * sy;
        const on = highlightedBlockIndex === globalIdx;
        const color = getStructureColor(block);
        return (
          <div
            key={globalIdx}
            style={{
              position: "absolute",
              left, top, width: w, height: h,
              border: on ? "2px solid rgba(34, 197, 94, 0.95)" : `2px solid ${hexToRgba(color, 0.55)}`,
              background: on ? "rgba(34, 197, 94, 0.22)" : hexToRgba(color, 0.08),
              borderRadius: 2,
              transition: "background 0.08s, border-color 0.08s",
              overflow: "visible",
            }}
          >
            {on && w > 30 && h > 16 && (
              <span style={{
                position: "absolute", top: -16, left: 0,
                fontSize: 9, color: color, whiteSpace: "nowrap",
                background: "#0d1117", padding: "0 3px", borderRadius: 2,
              }}>
                {block.structure_type || block.type}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}

function UploadCanvas({
  file,
  setFile,
  preview,
  setPreview,
  blocks,
  highlightedBlockIndex,
  setHighlightedBlockIndex,
  txtContent,
  setTxtContent,
  setPointerMeta,
  fullText,
  blockSpans,
  onClearSession,
}) {
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef(null);
  const imageRef = useRef(null);
  const txtPreRef = useRef(null);
  const imgWrapRef = useRef(null);
  const [imgDisplay, setImgDisplay] = useState({ w: 0, h: 0 });

  const measureImage = useCallback(() => {
    const img = imageRef.current;
    if (!img?.complete || !img?.naturalWidth) return;
    const r = img.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) {
      setImgDisplay({ w: r.width, h: r.height });
    }
  }, []);

  useEffect(() => {
    measureImage();
    window.addEventListener("resize", measureImage);
    const ro = new ResizeObserver(() => measureImage());
    if (imgWrapRef.current) ro.observe(imgWrapRef.current);
    return () => {
      window.removeEventListener("resize", measureImage);
      ro.disconnect();
    };
  }, [measureImage]);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) validateAndSetFile(droppedFile);
  }, []);

  const handleDragOver = (e) => { e.preventDefault(); setDragOver(true); };
  const handleDragLeave = () => setDragOver(false);

  const validateAndSetFile = (f) => {
    const ext = "." + f.name.split(".").pop().toLowerCase();
    if (!SUPPORTED_TYPES.includes(ext)) {
      alert("Unsupported file type. Please upload PDF, PNG, JPG, JPEG, WebP, or TXT.");
      return;
    }
    if (f.size > MAX_FILE_SIZE) {
      alert("File too large. Maximum size is 50MB.");
      return;
    }
    setFile(f);
    setTxtContent("");
    if (f.type.startsWith("image/")) {
      const reader = new FileReader();
      reader.onload = (e) => setPreview(e.target.result);
      reader.readAsDataURL(f);
    } else if (f.type === "application/pdf") {
      setPreview(URL.createObjectURL(f));
    } else if (ext === ".txt" || f.type === "text/plain") {
      setPreview(null);
      const reader = new FileReader();
      reader.onload = (e) => setTxtContent(e.target.result ?? "");
      reader.readAsText(f, "UTF-8");
    } else {
      setPreview(null);
    }
  };

  const handleChange = (e) => {
    const f = e.target.files?.[0];
    if (f) validateAndSetFile(f);
  };

  const handleImageMouseMove = (e) => {
    if (!blocks?.length || !imageRef.current) return;
    const img = imageRef.current;
    if (!img.complete || !img.naturalWidth) return;
    const rect = img.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;
    const scaleX = img.naturalWidth / rect.width;
    const scaleY = img.naturalHeight / rect.height;
    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;
    let foundIndex = null;
    for (let i = 0; i < blocks.length; i++) {
      const r = bboxToRect(blocks[i].bbox);
      if (r && pointInRect(x, y, r)) {
        foundIndex = i;
        break;
      }
    }
    if (foundIndex == null && blocks.length === 1 && !bboxToRect(blocks[0].bbox)) {
      if (x >= 0 && y >= 0 && x <= img.naturalWidth && y <= img.naturalHeight) foundIndex = 0;
    }
    setHighlightedBlockIndex(foundIndex);
    const span = foundIndex != null ? blockSpans[foundIndex] : null;
    const offset = span?.start ?? null;
    const { line, col } = lineColAtOffset(fullText || "", offset ?? 0);
    setPointerMeta({
      page: blocks[foundIndex]?.page ?? 1,
      line: offset != null ? line : null,
      col: offset != null ? col : null,
      charOffset: offset,
      blockIndex: foundIndex,
      region: "source",
    });
  };

  const handleImageMouseLeave = () => {
    setHighlightedBlockIndex(null);
    setPointerMeta(null);
  };

  const handleTxtMouseMove = (e) => {
    if (!txtContent || !blocks?.length) return;
    const pre = txtPreRef.current;
    const offset = offsetFromPointInTextElement(pre, e.clientX, e.clientY);
    if (offset == null) return;
    let idx = null;
    for (let i = 0; i < blockSpans.length; i++) {
      const s = blockSpans[i];
      if (s.start != null && s.end != null && offset >= s.start && offset < s.end) {
        idx = i;
        break;
      }
    }
    if (idx == null && blocks.length === 1) idx = 0;
    setHighlightedBlockIndex(idx);
    const { line, col } = lineColAtOffset(txtContent, offset);
    setPointerMeta({
      page: 1,
      line,
      col,
      charOffset: offset,
      blockIndex: idx,
      region: "source",
    });
  };

  const handleTxtMouseLeave = () => {
    setHighlightedBlockIndex(null);
    setPointerMeta(null);
  };

  const isImage = file?.type?.startsWith("image/");
  const isPdf = file?.type === "application/pdf";
  const isTxt = file && (file.type === "text/plain" || file.name?.toLowerCase().endsWith(".txt"));

  return (
    <div style={{
      flex: 1, display: "flex", flexDirection: "column", background: "#0d1117", padding: 24
    }}>
      <div style={{ marginBottom: 8, fontSize: 13, color: "#8b949e", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span>Source Document</span>
        {file && (
          <button
            onClick={onClearSession}
            title="Clear session and start over"
            style={{
              background: "transparent", border: "1px solid #30363d", borderRadius: 6,
              color: "#8b949e", cursor: "pointer", fontSize: 12, padding: "3px 10px",
              display: "flex", alignItems: "center", gap: 4,
              transition: "color 0.15s, border-color 0.15s",
            }}
            onMouseEnter={e => { e.currentTarget.style.color = "#ef4444"; e.currentTarget.style.borderColor = "#ef4444"; }}
            onMouseLeave={e => { e.currentTarget.style.color = "#8b949e"; e.currentTarget.style.borderColor = "#30363d"; }}
          >
            × Start Over
          </button>
        )}
      </div>
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => fileInputRef.current?.click()}
        style={{
          flex: 1, border: dragOver ? "2px dashed #6366f1" : "2px dashed #30363d",
          borderRadius: 12, display: "flex", flexDirection: "column", alignItems: "center",
          justifyContent: "center", cursor: "pointer", transition: "all 0.2s",
          background: dragOver ? "rgba(99, 102, 241, 0.1)" : "#161b22",
          position: "relative", overflow: "auto"
        }}
      >
        <input ref={fileInputRef} type="file" accept=".pdf,image/*,.txt" onChange={handleChange} style={{ display: "none" }} />
        {!file ? (
          <>
            <div style={{ fontSize: 48, marginBottom: 16, color: "#8b949e" }}>📄</div>
            <div style={{ fontSize: 16, color: "#e6edf3", marginBottom: 8 }}>Drop file here or click to upload</div>
            <div style={{ fontSize: 12, color: "#8b949e" }}>PDF, PNG, JPG, JPEG, WebP, TXT</div>
          </>
        ) : (
          <div
            onClick={(e) => e.stopPropagation()}
            style={{ width: "100%", height: "100%", position: "relative", display: "flex", alignItems: "flex-start", justifyContent: "center", padding: 16, cursor: "default" }}
          >
            {isImage && preview && (
              <div
                ref={imgWrapRef}
                style={{ position: "relative", display: "inline-block", maxWidth: "100%", maxHeight: "calc(100vh - 200px)", overflow: "auto" }}
              >
                <img
                  ref={imageRef}
                  src={preview}
                  alt="preview"
                  style={{ maxWidth: "100%", height: "auto", display: "block", cursor: "crosshair" }}
                  onLoad={measureImage}
                  onMouseMove={handleImageMouseMove}
                  onMouseLeave={handleImageMouseLeave}
                />
                {blocks?.length > 0 && imgDisplay.w > 0 && imgDisplay.h > 0 && (
                  <BboxOverlay
                    blocks={blocks}
                    naturalW={imageRef.current?.naturalWidth || 1}
                    naturalH={imageRef.current?.naturalHeight || 1}
                    highlightedBlockIndex={highlightedBlockIndex}
                    displayW={imgDisplay.w}
                    displayH={imgDisplay.h}
                    pageNum={null}
                  />
                )}
              </div>
            )}
            {isPdf && preview && (
              <div
                style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}
                onMouseLeave={() => { setHighlightedBlockIndex(null); setPointerMeta(null); }}
              >
                <iframe src={preview} style={{ width: "100%", height: "100%", border: "none" }} />
              </div>
            )}
            {isTxt && (
              <pre
                ref={txtPreRef}
                onMouseMove={handleTxtMouseMove}
                onMouseLeave={handleTxtMouseLeave}
                style={{
                  margin: 0,
                  padding: 12,
                  maxWidth: "100%",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  fontSize: 13,
                  fontFamily: "ui-monospace, monospace",
                  color: "#e6edf3",
                  textAlign: "left",
                  cursor: "text",
                  userSelect: "text",
                }}
              >
                {txtContent || "Reading…"}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ProgressPanel({ progress, events }) {
  const stageLabels = {
    upload_received: "📥 File received",
    model_loading: "⏳ Loading OCR models",
    page_start: "📄 Processing page",
    page_native_text: "📝 Extracting native text",
    page_ocr_done: "✅ OCR hints extracted",
    page_vlm_start: "🧠 VLM analyzing",
    page_vlm_done: "✅ VLM analysis complete",
    ocr_fallback: "🔄 Falling back to OCR",
    structure_fallback: "📐 Running layout analysis",
    complete: "🎉 Extraction complete",
    error: "❌ Processing error",
  };

  const pct = Math.round((progress || 0) * 100);
  const lastEvents = events.slice(-8);
  const hasPages = events.some(e => e.page != null && e.total_pages != null);
  const currentPage = events.findLast(e => e.page != null)?.page;
  const totalPages = events.findLast(e => e.total_pages != null)?.total_pages;
  const currentEngine = events.findLast(e => e.engine != null)?.engine;

  const engineLabel = {
    vlm: "VLM",
    ocr: "几何OCR",
    structure: "PPStructure",
    native_text: "Native PDF text",
  };

  return (
    <div style={{
      flex: 1, overflow: "auto", background: "#161b22", borderRadius: 8, padding: 20,
      display: "flex", flexDirection: "column", gap: 16,
    }}>
      <div style={{ fontSize: 13, color: "#8b949e" }}>Processing document…</div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "#8b949e" }}>
          <span>{stageLabels[events[events.length - 1]?.stage] || events[events.length - 1]?.stage || "Starting…"}</span>
          <span>{pct}%</span>
        </div>
        <div style={{
          width: "100%", height: 6, background: "#262c36", borderRadius: 3, overflow: "hidden",
        }}>
          <div style={{
            width: `${pct}%`, height: "100%", borderRadius: 3,
            background: pct >= 100 ? "#34d399" : "#6366f1",
            transition: "width 0.3s ease, background 0.3s",
          }} />
        </div>
      </div>

      {hasPages && currentPage != null && (
        <div style={{
          display: "flex", gap: 12, fontSize: 12, color: "#6b7280", flexWrap: "wrap",
        }}>
          <span>Page {currentPage} / {totalPages}</span>
          {currentEngine && <span>Engine: {engineLabel[currentEngine] || currentEngine}</span>}
        </div>
      )}

      <div style={{
        background: "#1c2128", borderRadius: 6, padding: 10, maxHeight: 240, overflow: "auto",
        fontSize: 11, lineHeight: 1.6,
      }}>
        {lastEvents.map((evt, i) => {
          const isError = evt.stage === "error";
          const isComplete = evt.stage === "complete";
          return (
            <div key={i} style={{
              color: isError ? "#f87171" : isComplete ? "#34d399" : "#8b949e",
              paddingLeft: evt.page != null ? 8 : 0,
              borderLeft: evt.page != null ? "2px solid #30363d" : "none",
            }}>
              {evt.message}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ResultPanel({
  result,
  loading,
  progress,
  progressEvents,
  error,
  onExport,
  onExportMarkdown,
  summary,
  summaryLoading,
  summaryError,
  onSummarize,
  vlmEnabled,
  highlightedBlockIndex,
  setHighlightedBlockIndex,
  activeTab,
  setActiveTab,
  blockSpans,
  setPointerMeta,
  rawPreRef,
}) {
  const tabs = [
    { id: "layout", label: "Layout" },
    { id: "structure", label: "Structure" },
    { id: "raw", label: "Raw Text" },
    { id: "table", label: "Table" },
    { id: "summary", label: "🤖 AI Summary" },
  ];

  const groupedBlocks = useMemo(() => {
    if (!result?.blocks) return {};
    const groups = {};
    result.blocks.forEach(block => {
      const key = block.page || 1;
      if (!groups[key]) groups[key] = [];
      groups[key].push(block);
    });
    return groups;
  }, [result]);

  const allBlocks = result?.blocks || [];

  const handleRawMouseMove = (e) => {
    if (!result?.text) return;
    const pre = rawPreRef.current;
    const offset = offsetFromPointInTextElement(pre, e.clientX, e.clientY);
    if (offset == null) return;
    let idx = null;
    for (let i = 0; i < blockSpans.length; i++) {
      const s = blockSpans[i];
      if (s.start != null && s.end != null && offset >= s.start && offset < s.end) {
        idx = i;
        break;
      }
    }
    setHighlightedBlockIndex(idx);
    const { line, col } = lineColAtOffset(result.text, offset);
    setPointerMeta({
      page: idx != null ? allBlocks[idx]?.page : null,
      line,
      col,
      charOffset: offset,
      blockIndex: idx,
      region: "raw",
    });
  };

  const handleRawMouseLeave = () => {
    setHighlightedBlockIndex(null);
    setPointerMeta(null);
  };

  const hl = highlightedBlockIndex != null ? blockSpans[highlightedBlockIndex] : null;

  return (
    <div style={{
      flex: 1, display: "flex", flexDirection: "column", background: "#0d1117", borderLeft: "1px solid #30363d", padding: 24
    }}>
      <div style={{ marginBottom: 8, fontSize: 13, color: "#8b949e" }}>Extraction Results</div>

      <div style={{ display: "flex", gap: 4, marginBottom: 16, background: "#161b22", padding: 4, borderRadius: 8 }}>
        {tabs.map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)} style={{
            flex: 1, padding: "8px 16px", border: "none", borderRadius: 6, cursor: "pointer",
            fontSize: 13, background: activeTab === tab.id ? "#262c36" : "transparent",
            color: activeTab === tab.id ? "#e6edf3" : "#8b949e"
          }}>
            {tab.label}
          </button>
        ))}
      </div>

      <div style={{ flex: 1, overflow: "auto", background: "#161b22", borderRadius: 8, padding: 16 }}>
        {loading && progress && (
          <ProgressPanel progress={progress} events={progressEvents} />
        )}
        {loading && !progress && <div style={{ color: "#8b949e", textAlign: "center", padding: 40 }}>Processing document...</div>}
        {error && <div style={{ color: "#ef4444", padding: 16 }}>Error: {error}</div>}
        {result?.cross_validation_summary && (
          <CrossValidationSummaryPanel summary={result.cross_validation_summary} />
        )}
        {result?.legal_field_diffs && (
          <LegalFieldDiffPanel diffs={result.legal_field_diffs} />
        )}
        {result?.notes?.length > 0 && (() => {
          const errorKeywords = ["失败", "异常"];
          const warningKeywords = ["差异", "遗漏", "过度分割", "过大", "建议复核", "不一致", "关键字段"];
          const categorized = { errors: [], warnings: [], infos: [] };
          result.notes.forEach(note => {
            if (errorKeywords.some(k => note.includes(k))) {
              categorized.errors.push(note);
            } else if (warningKeywords.some(k => note.includes(k))) {
              categorized.warnings.push(note);
            } else {
              categorized.infos.push(note);
            }
          });
          return (
            <>
              {categorized.errors.length > 0 && (
                <div style={{
                  background: "rgba(239, 68, 68, 0.1)", border: "1px solid rgba(239, 68, 68, 0.3)",
                  borderRadius: 8, padding: "10px 14px", marginBottom: 8, fontSize: 13, color: "#f87171",
                  lineHeight: 1.6,
                }}>
                  ❌ {categorized.errors.map((note, i) => <div key={i}>{note}</div>)}
                </div>
              )}
              {categorized.warnings.length > 0 && (
                <div style={{
                  background: "rgba(245, 158, 11, 0.1)", border: "1px solid rgba(245, 158, 11, 0.3)",
                  borderRadius: 8, padding: "10px 14px", marginBottom: 8, fontSize: 13, color: "#fbbf24",
                  lineHeight: 1.6,
                }}>
                  ⚠️ {categorized.warnings.map((note, i) => <div key={i}>{note}</div>)}
                </div>
              )}
              {categorized.infos.length > 0 && (
                <div style={{
                  background: "rgba(99, 102, 241, 0.1)", border: "1px solid rgba(99, 102, 241, 0.3)",
                  borderRadius: 8, padding: "10px 14px", marginBottom: 8, fontSize: 13, color: "#a5b4fc",
                  lineHeight: 1.6,
                }}>
                  ℹ️ {categorized.infos.map((note, i) => <div key={i}>{note}</div>)}
                </div>
              )}
            </>
          );
        })()}
        {!result && !loading && !error && <div style={{ color: "#8b949e", textAlign: "center", padding: 40 }}>Upload a document and click Process to begin</div>}

        {result && activeTab === "layout" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {Object.entries(groupedBlocks).map(([page, pblocks]) => (
              <div key={page} style={{ background: "#1c2128", borderRadius: 8, padding: 12 }}>
                <div style={{ fontSize: 12, color: "#8b949e", marginBottom: 8 }}>Page {page}</div>
                {pblocks.map((block, i) => {
                  const globalIndex = allBlocks.indexOf(block);
                  const isHighlighted = highlightedBlockIndex === globalIndex;
                  const blockColor = getStructureColor(block);
                  const hierarchyIndent = (block.hierarchy_level || 0) * 12;
                  const hasChildren = block.relations?.some(r => r.startsWith("child:"));
                  const hasParent = !!block.parent_id;
                  const legalDiffHit = blockTouchesLegalDiff(block, result.legal_field_diffs);
                  const cvStatus = block.cross_validation?.status;
                  const cvMeta = cvStatus ? cvStatusMeta(cvStatus) : null;
                  const cvMismatch = cvStatus === "mismatch";
                  return (
                    <div
                      key={i}
                      onMouseEnter={() => {
                        setHighlightedBlockIndex(globalIndex);
                        const s = blockSpans[globalIndex];
                        const off = s?.start;
                        const { line, col } = lineColAtOffset(result.text, off ?? 0);
                        setPointerMeta({
                          page: block.page,
                          line: off != null ? line : null,
                          col: off != null ? col : null,
                          charOffset: off ?? null,
                          blockIndex: globalIndex,
                          region: "layout",
                        });
                      }}
                      onMouseLeave={() => {
                        setHighlightedBlockIndex(null);
                        setPointerMeta(null);
                      }}
                      style={{
                        background: isHighlighted ? "rgba(34, 197, 94, 0.2)" : (block.structure_type === "table" ? "rgba(245, 158, 11, 0.1)" : "#262c36"),
                        border: isHighlighted ? "1px solid rgba(34, 197, 94, 0.7)" : (block.structure_type === "table" ? "1px solid rgba(245, 158, 11, 0.3)" : "1px solid #30363d"),
                        borderLeft: (legalDiffHit || cvMismatch)
                          ? "3px solid #f87171"
                          : (cvStatus === "match" ? "3px solid #34d399"
                          : (hasParent ? `3px solid ${blockColor}` : undefined)),
                        borderRadius: 6, padding: 10, paddingLeft: hasParent ? 10 + hierarchyIndent : 10 + hierarchyIndent, marginBottom: 8, display: "flex", alignItems: "flex-start", gap: 10,
                        cursor: "pointer",
                        transition: "background 0.1s, border-color 0.1s"
                      }}
                    >
                      <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 28 }}>
                        {block.reading_order != null && (
                          <span style={{
                            fontSize: 9, padding: "1px 4px", borderRadius: 3, background: "#374151", color: "#9ca3af", whiteSpace: "nowrap", textAlign: "center"
                          }}>
                            {block.reading_order + 1}
                          </span>
                        )}
                        <span style={{
                          fontSize: 10, padding: "2px 6px", borderRadius: 4, background: blockColor, color: "#fff", whiteSpace: "nowrap"
                        }}>{block.structure_type || block.type}</span>
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 13, color: "#e6edf3", whiteSpace: "pre-wrap" }}>{block.text}</div>
                        <div style={{ display: "flex", gap: 8, marginTop: 4, flexWrap: "wrap" }}>
                          {block.confidence != null && (
                            <span style={{ fontSize: 11, color: "#8b949e" }}>
                              Conf: {(block.confidence * 100).toFixed(1)}%
                            </span>
                          )}
                          {block.group_id && block.group_id !== "single" && (
                            <span style={{ fontSize: 10, color: "#6b7280", fontStyle: "italic" }}>
                              {block.group_id}
                            </span>
                          )}
                          {legalDiffHit && (
                            <span style={{
                              fontSize: 10, color: "#f87171",
                              background: "rgba(248,113,113,0.12)",
                              padding: "1px 6px", borderRadius: 4,
                            }}>
                              案号/金额 OCR≠VLM
                            </span>
                          )}
                          {cvMeta && (
                            <span style={{
                              fontSize: 10, color: cvMeta.color,
                              background: cvMeta.bg,
                              padding: "1px 6px", borderRadius: 4,
                            }}
                              title={cvStatus === "mismatch"
                                ? `主: ${block.cross_validation.primary_text}\n副: ${block.cross_validation.secondary_text}\n相似度: ${(block.cross_validation.similarity * 100).toFixed(0)}%`
                                : cvMeta.label}
                            >
                              {cvMeta.label}
                            </span>
                          )}
                          {hasChildren && (
                            <span style={{ fontSize: 10, color: "#6b7280" }}>
                              ▸ {block.relations.filter(r => r.startsWith("child:")).length} child(ren)
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        )}

        {result && activeTab === "structure" && (
          <StructureView
            blocks={allBlocks}
            pageInfos={result.page_infos}
            highlightedBlockIndex={highlightedBlockIndex}
            setHighlightedBlockIndex={setHighlightedBlockIndex}
          />
        )}

        {result && activeTab === "raw" && (
          <pre
            ref={rawPreRef}
            onMouseMove={handleRawMouseMove}
            onMouseLeave={handleRawMouseLeave}
            style={{
              margin: 0,
              fontSize: 13,
              color: "#e6edf3",
              whiteSpace: "pre-wrap",
              fontFamily: "ui-monospace, monospace",
              cursor: "text",
              lineHeight: 1.5,
            }}
          >
            {hl?.start != null && hl?.end != null ? (
              <>
                {result.text.slice(0, hl.start)}
                <mark style={{
                  background: "rgba(34, 197, 94, 0.35)",
                  color: "inherit",
                  borderRadius: 2,
                  padding: "0 2px",
                }}>
                  {result.text.slice(hl.start, hl.end)}
                </mark>
                {result.text.slice(hl.end)}
              </>
            ) : (
              result.text
            )}
          </pre>
        )}

        {result && activeTab === "summary" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {/* Engine badge */}
            {result.vlm_used != null && (
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <span style={{
                  fontSize: 11, fontWeight: 700, padding: "3px 10px", borderRadius: 20,
                  background: result.vlm_used ? "rgba(52,211,153,0.15)" : "rgba(99,102,241,0.15)",
                  color: result.vlm_used ? "#34d399" : "#a5b4fc",
                  border: `1px solid ${result.vlm_used ? "rgba(52,211,153,0.35)" : "rgba(99,102,241,0.35)"}`,
                }}>
                  {result.vlm_used ? `✦ VLM · ${result.vlm_engine || "enabled"}` : "⊕ OCR (geometric fallback)"}
                </span>
                {!result.vlm_used && <span style={{ fontSize: 12, color: "#8b949e" }}>VLM 未启用或调用失败，当前为几何布局提取结果</span>}
                {result.vlm_used && result.blocks?.length > 0 && (() => {
                  const confs = result.blocks.filter(b => b.confidence != null).map(b => b.confidence);
                  if (!confs.length) return null;
                  const avg = confs.reduce((a, b) => a + b, 0) / confs.length;
                  const low = confs.filter(c => c < 0.7).length;
                  const color = avg >= 0.9 ? "#34d399" : avg >= 0.8 ? "#fbbf24" : "#f87171";
                  return (
                    <span style={{ fontSize: 11, color: "#8b949e" }}>
                      置信度: <strong style={{ color }}>{(avg * 100).toFixed(1)}%</strong>
                      {low > 0 && <span style={{ color: "#f87171", marginLeft: 6 }}>({low} 块低于 70%，建议复核)</span>}
                    </span>
                  );
                })()}
              </div>
            )}

            {/* 精读原文：与「生成摘要」同次 VLM 产出；原始拼接见 Raw Text 标签 */}
            <div>
              <div style={{ fontSize: 12, color: "#8b949e", marginBottom: 8, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                {summary?.readable_transcript ? "📄 精读文本（AI 去噪）" : "📄 可读原文"}
              </div>
              {summary?.readable_transcript ? (
                <pre style={{
                  background: "#1c2128", borderRadius: 8, padding: 14, fontSize: 13,
                  color: "#e6edf3", whiteSpace: "pre-wrap", wordBreak: "break-word",
                  lineHeight: 1.7, maxHeight: 480, overflow: "auto",
                  border: "1px solid rgba(52,211,153,0.25)",
                }}>{summary.readable_transcript}</pre>
              ) : summary && result.text ? (
                <>
                  <div style={{ fontSize: 12, color: "#fbbf24", marginBottom: 8, lineHeight: 1.5 }}>
                    本次摘要未返回 readable_transcript 字段，暂显示与 Raw Text 相同的原始拼接文本。
                  </div>
                  <pre style={{
                    background: "#1c2128", borderRadius: 8, padding: 14, fontSize: 13,
                    color: "#e6edf3", whiteSpace: "pre-wrap", wordBreak: "break-word",
                    lineHeight: 1.7, maxHeight: 260, overflow: "auto",
                    border: "1px solid #30363d",
                  }}>{result.text}</pre>
                </>
              ) : result.text ? (
                <div style={{
                  background: "#1c2128", borderRadius: 8, padding: 14, fontSize: 13,
                  color: "#9ca3af", lineHeight: 1.7, border: "1px solid #30363d",
                }}>
                  逐字提取结果（含版面/时间戳等噪音）请在 <strong style={{ color: "#e6edf3" }}>Raw Text</strong> 标签页查看。
                  <br /><br />
                  点击下方 <strong style={{ color: "#a5b4fc" }}>生成摘要</strong> 后，此处将显示与结构化摘要<strong style={{ color: "#34d399" }}>同一次</strong> VLM 调用产出的<strong style={{ color: "#e6edf3" }}>去噪可读原文</strong>（readable_transcript），便于阅读与核对。
                </div>
              ) : null}
            </div>

            {/* Block type breakdown */}
            {result.blocks?.length > 0 && (() => {
              const counts = {};
              result.blocks.forEach(b => { counts[b.type] = (counts[b.type] || 0) + 1; });
              return (
                <div>
                  <div style={{ fontSize: 12, color: "#8b949e", marginBottom: 8, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>🗂 结构概览</div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                    {Object.entries(counts).map(([type, n]) => (
                      <span key={type} style={{ background: "#262c36", color: "#e6edf3", borderRadius: 6, padding: "4px 12px", fontSize: 12 }}>
                        {type}: <strong>{n}</strong>
                      </span>
                    ))}
                  </div>
                </div>
              );
            })()}

            {/* AI Summary section */}
            <div style={{ borderTop: "1px solid #30363d", paddingTop: 14 }}>
              <div style={{ fontSize: 12, color: "#8b949e", marginBottom: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>🤖 AI 摘要</div>
              {!vlmEnabled && (
                <div style={{ background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.3)", borderRadius: 8, padding: 14, fontSize: 13, color: "#a5b4fc" }}>
                  💡 启用 VLM 后才能生成 AI 摘要。请前往 <strong>VLM Config</strong> 配置并启用。
                </div>
              )}
              {vlmEnabled && !summary && !summaryLoading && !summaryError && (
                <div style={{ textAlign: "center", padding: "24px 0" }}>
                  <div style={{ fontSize: 13, color: "#8b949e", marginBottom: 14 }}>让 VLM 对整个文档进行语义理解和摘要生成。</div>
                  <button
                    onClick={onSummarize}
                    style={{ padding: "10px 24px", background: "#6366f1", color: "#fff", border: "none", borderRadius: 8, cursor: "pointer", fontSize: 14, fontWeight: 600 }}
                  >
                    ✨ 生成摘要与精读文本
                  </button>
                </div>
              )}
              {summaryLoading && (
                <div style={{ textAlign: "center", padding: 20, color: "#8b949e", fontSize: 14 }}>VLM 分析中，请稍候…</div>
              )}
              {summaryError && (
                <div style={{ background: "rgba(248,113,113,0.1)", border: "1px solid rgba(248,113,113,0.3)", borderRadius: 8, padding: 14, fontSize: 13, color: "#f87171" }}>
                  ⚠️ {summaryError}
                </div>
              )}
              {summary && (
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    {summary.court && (
                      <span style={{ background: "rgba(99,102,241,0.2)", border: "1px solid rgba(99,102,241,0.4)", color: "#a5b4fc", borderRadius: 20, padding: "4px 14px", fontSize: 12, fontWeight: 600 }}>
                        🏛️ {summary.court}
                      </span>
                    )}
                    {summary.case_number && (
                      <span style={{ background: "rgba(52,211,153,0.15)", border: "1px solid rgba(52,211,153,0.3)", color: "#34d399", borderRadius: 20, padding: "4px 14px", fontSize: 12, fontWeight: 600 }}>
                        📄 {summary.case_number}
                      </span>
                    )}
                    {summary.word_count_estimate > 0 && (
                      <span style={{ background: "#262c36", color: "#8b949e", borderRadius: 20, padding: "4px 14px", fontSize: 12 }}>~{summary.word_count_estimate} words</span>
                    )}
                  </div>
                  {summary.main_ruling && (
                    <div style={{ background: "#1c2128", borderRadius: 8, padding: 16, fontSize: 14, color: "#e6edf3", lineHeight: 1.7, border: "1px solid #30363d" }}>
                      <div style={{ fontSize: 12, color: "#8b949e", marginBottom: 8, fontWeight: 600 }}>核心判决 / 摘要事实</div>
                      {summary.main_ruling}
                    </div>
                  )}
                  {summary.plaintiff_defendant?.length > 0 && (
                    <div>
                      <div style={{ fontSize: 12, color: "#8b949e", marginBottom: 8 }}>涉案当事人</div>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                        {summary.plaintiff_defendant.map((p, i) => (
                          <span key={i} style={{ background: "#262c36", color: "#e6edf3", borderRadius: 6, padding: "4px 12px", fontSize: 13 }}>👤 {p}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  <button
                    onClick={onSummarize}
                    style={{ alignSelf: "flex-start", background: "transparent", border: "1px solid #30363d", borderRadius: 6, color: "#8b949e", cursor: "pointer", fontSize: 12, padding: "6px 14px" }}
                  >
                    🔄 重新生成
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
        {result && activeTab === "table" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {(() => {
              const tableBlocks = result.blocks.filter(b => b.table_html || b.structure_type === "table");
              if (!tableBlocks.length) {
                return (
                  <div style={{ color: "#8b949e", textAlign: "center", padding: 40 }}>
                    No tables detected in this document
                  </div>
                );
              }
              return tableBlocks.map((block, i) => (
                <div key={i} style={{ background: "#1c2128", borderRadius: 8, padding: 12 }}>
                  <div style={{ fontSize: 12, color: "#8b949e", marginBottom: 8 }}>
                    Table {i + 1} {block.confidence != null ? `· Conf: ${(block.confidence * 100).toFixed(1)}%` : ""}
                  </div>
                  {block.table_html ? (
                    <div style={{
                      overflow: "auto",
                      "& table": { width: "100%", borderCollapse: "collapse" },
                    }}>
                      <div dangerouslySetInnerHTML={{ __html: block.table_html }} style={{
                        color: "#e6edf3",
                      }} />
                      <style>{`
                        .structure-table table { width: 100%; border-collapse: collapse; }
                        .structure-table th, .structure-table td { border: 1px solid #30363d; padding: 8px 12px; text-align: left; font-size: 13px; }
                        .structure-table th { background: #262c36; color: #e6edf3; font-weight: 600; }
                        .structure-table tr:nth-child(even) { background: #1c2128; }
                        .structure-table tr:nth-child(odd) { background: #21262d; }
                        .structure-table tr:hover { background: #2d333b; }
                      `}</style>
                      <div className="structure-table" dangerouslySetInnerHTML={{ __html: block.table_html }} />
                    </div>
                  ) : (
                    <div style={{ fontSize: 13, color: "#e6edf3", whiteSpace: "pre-wrap" }}>
                      {block.text}
                    </div>
                  )}
                </div>
              ));
            })()}
          </div>
        )}
      </div>

      {result && (
        <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ padding: 12, background: "#161b22", borderRadius: 8, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ fontSize: 12, color: "#8b949e" }}>
              {result.pages} page(s) • {result.blocks.length} blocks • {result.checksum?.slice(0, 12)}...
            </div>
            <button onClick={onExport} style={{
              padding: "8px 16px", background: "#6366f1", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer", fontSize: 13
            }}>
              Export JSON
            </button>
            <button onClick={onExportMarkdown} style={{
              padding: "8px 16px", background: "transparent", color: "#e6edf3", border: "1px solid #30363d", borderRadius: 6, cursor: "pointer", fontSize: 13
            }}>
              Export Markdown
            </button>
          </div>
          <div style={{ padding: 8, background: "#161b22", borderRadius: 8, display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <span style={{ fontSize: 11, color: "#6b7280" }}>Structure:</span>
            {Object.entries(STRUCTURE_COLORS).slice(0, 6).map(([type, color]) => (
              <span key={type} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11 }}>
                <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: color }} />
                <span style={{ color: "#8b949e", textTransform: "capitalize" }}>{type}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function App() {
  const [activeView, setActiveView] = useState("workspace");
  const [vlmConfig, setVlmConfig] = useState(null);
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [txtContent, setTxtContent] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState(0);
  const [progressEvents, setProgressEvents] = useState([]);
  const [highlightedBlockIndex, setHighlightedBlockIndex] = useState(null);
  const [pointerMeta, setPointerMeta] = useState(null);
  const [summary, setSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState("");
  const [activeTab, setActiveTab] = useState("layout");
  const rawPreRef = useRef(null);

  const blockSpans = useMemo(
    () => computeBlockSpans(result?.text ?? "", result?.blocks ?? []),
    [result]
  );

  const handleProcess = async () => {
    if (!file) return;
    setLoading(true);
    setError("");
    setProgress(0);
    setProgressEvents([]);
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_BASE}/api/extract-stream`, { method: "POST", body: formData });
      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(`HTTP ${res.status}: ${errorText}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (let i = 0; i < lines.length; i++) {
          if (lines[i].startsWith("data: ")) {
            try {
              const data = JSON.parse(lines[i].slice(6));
              setProgress(data.progress || 0);
              setProgressEvents(prev => [...prev, data]);

              if (data.stage === "complete" && data.extra?.result) {
                setResult(data.extra.result);
              }
              if (data.stage === "error") {
                throw new Error(data.message);
              }
            } catch (parseErr) {
              if (parseErr.message && !parseErr.message.startsWith("HTTP")) throw parseErr;
            }
          }
        }
      }
    } catch (err) {
      const errorMessage = err.message || String(err);
      if (errorMessage.includes("Failed to fetch") || err instanceof TypeError) {
        setError(`无法连接后端服务 (${API_BASE})。请确保后端服务已启动：
          cd backend && uvicorn app.main:app --reload --port 8000`);
      } else {
        setError(errorMessage);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleExport = () => {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${file?.name || "extraction"}_result.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleExportMarkdown = () => {
    if (!result) return;
    const lines = [];
    lines.push(`# ${(file?.name || "Document").replace(/\.[^.]+$/, "")}\n`);
    const grouped = {};
    result.blocks.forEach(block => {
      const page = block.page || 1;
      if (!grouped[page]) grouped[page] = [];
      grouped[page].push(block);
    });
    const pageKeys = Object.keys(grouped);
    pageKeys.forEach(page => {
      if (pageKeys.length > 1) {
        lines.push(`\n---\n\n## Page ${page}\n`);
      }
      grouped[page].forEach(block => {
        const stype = block.structure_type || block.type;
        const text = (block.text || "").trim();
        if (!text && !block.table_html) return;
        if (stype === "title" || stype === "doc_title" || stype === "paragraph_title") {
          const hlevel = block.hierarchy_level;
          const md_level = hlevel <= 0 ? 2 : hlevel <= 1 ? 3 : 4;
          lines.push(`${"#".repeat(md_level)} ${text}\n`);
        } else if (stype === "table" && block.table_html) {
          lines.push(`\n${block.table_html}\n`);
        } else if (stype === "caption" || stype === "figure_caption" || stype === "table_caption") {
          lines.push(`> *${text}*\n`);
        } else if (stype === "equation" || stype === "formula") {
          lines.push(`\n$$\n${text}\n$$\n`);
        } else if (stype === "list") {
          text.split("\n").forEach(item => {
            const trimmed = item.trim();
            if (trimmed) lines.push(`- ${trimmed}`);
          });
          lines.push("");
        } else if (stype === "header") {
          // skip page headers from output
        } else if (stype === "footer") {
          // skip page footers from output
        } else if (stype === "footnote") {
          lines.push(`[^]: ${text}\n`);
        } else {
          lines.push(`${text}\n`);
        }
      });
    });
    if (result.notes?.length) {
      lines.push(`\n---\n\n> **Processing Notes:** ${result.notes.join(" | ")}\n`);
    }
    const md = lines.join("\n");
    const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${(file?.name || "extraction").replace(/\.[^.]+$/, "")}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Just navigate to workspace — state (file, result) is preserved so the
  // user can switch between Config / History / etc. and come back without
  // losing their work. Explicit reset is via the "× Start Over" button.
  const handleNewExtraction = () => {
    setActiveView("workspace");
  };

  const handleSummarize = async () => {
    if (!file) return;
    setSummaryLoading(true);
    setSummaryError("");
    setSummary(null);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await fetch(`${API_BASE}/api/summarize`, { method: "POST", body: formData });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(detail.detail || `HTTP ${res.status}`);
      }
      setSummary(await res.json());
    } catch (err) {
      setSummaryError(err.message || String(err));
    } finally {
      setSummaryLoading(false);
    }
  };

  const handleClearSession = () => {
    setFile(null);
    setPreview(null);
    setTxtContent("");
    setResult(null);
    setError("");
    setProgress(0);
    setProgressEvents([]);
    setHighlightedBlockIndex(null);
    setPointerMeta(null);
    setActiveTab("layout");
    setSummary(null);
    setSummaryError("");
  };

  const avgConfidence = useMemo(() => {
    if (!result?.blocks?.length) return 0;
    const withConf = result.blocks.filter(b => b.confidence != null);
    if (!withConf.length) return 0;
    return withConf.reduce((a, b) => a + b.confidence, 0) / withConf.length * 100;
  }, [result]);

  const pointerLabel = useMemo(() => {
    if (!pointerMeta) return "Hover source, layout, or raw text to sync highlight";
    const { page, line, col, charOffset, blockIndex, region } = pointerMeta;
    const parts = [];
    if (page != null) parts.push(`Page ${page}`);
    if (line != null) parts.push(`Line ${line}`);
    if (col != null) parts.push(`Col ${col}`);
    if (charOffset != null) parts.push(`Char ${charOffset}`);
    if (blockIndex != null) parts.push(`Block #${blockIndex + 1}`);
    if (region) parts.push(region);
    return parts.join(" · ");
  }, [pointerMeta]);

  useEffect(() => {
    let cancelled = false;

    const loadVlmConfig = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/vlm-config`);
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled) setVlmConfig(data);
      } catch {
        // Keep the workspace usable even if the config endpoint is temporarily unavailable.
      }
    };

    loadVlmConfig();
    return () => {
      cancelled = true;
    };
  }, []);

  const engineLabel = useMemo(() => {
    if (!vlmConfig) return result ? "OCR" : "Ready";
    if (!vlmConfig.enabled) return "OCR (geometry)";
    const provider = vlmConfig.provider || "vlm";
    const model = vlmConfig.model || "custom";
    return `VLM · ${provider} / ${model}`;
  }, [result, vlmConfig]);

  return (
    <div style={{ display: "flex", height: "100vh", background: "#0f1419" }}>
      <Sidebar activeView={activeView} setActiveView={setActiveView} onNewExtraction={handleNewExtraction} />
      <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        <Header activeView={activeView} />
        {activeView === "workspace" ? (
          <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
            <UploadCanvas
              file={file} setFile={setFile}
              preview={preview} setPreview={setPreview}
              blocks={result?.blocks}
              highlightedBlockIndex={highlightedBlockIndex}
              setHighlightedBlockIndex={setHighlightedBlockIndex}
              txtContent={txtContent}
              setTxtContent={setTxtContent}
              setPointerMeta={setPointerMeta}
              fullText={result?.text ?? ""}
              blockSpans={blockSpans}
              onClearSession={handleClearSession}
            />
            <ResultPanel
              result={result}
              loading={loading}
              progress={progress}
              progressEvents={progressEvents}
              error={error}
              onExport={handleExport}
              onExportMarkdown={handleExportMarkdown}
              summary={summary}
              summaryLoading={summaryLoading}
              summaryError={summaryError}
              onSummarize={handleSummarize}
              vlmEnabled={!!vlmConfig?.enabled}
              highlightedBlockIndex={highlightedBlockIndex}
              setHighlightedBlockIndex={setHighlightedBlockIndex}
              activeTab={activeTab}
              setActiveTab={setActiveTab}
              blockSpans={blockSpans}
              setPointerMeta={setPointerMeta}
              rawPreRef={rawPreRef}
            />
          </div>
        ) : activeView === "config" ? (
          <ConfigPanel vlmConfig={vlmConfig} setVlmConfig={setVlmConfig} />
        ) : (
          <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", background: "#0d1117", color: "#8b949e", fontSize: 14 }}>
            {activeView} view is not implemented in this demo yet.
          </div>
        )}
        <div style={{
          height: 40, background: "#161b22", borderTop: "1px solid #30363d",
          display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 24px", fontSize: 12, color: "#8b949e"
        }}>
          <div style={{ display: "flex", gap: 16, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1, marginRight: 16 }}>
            <span title={pointerLabel}>{pointerLabel}</span>
          </div>
          <div style={{ display: "flex", gap: 16, flexShrink: 0 }}>
            <span>Engine: {engineLabel}</span>
            {result && <span>Conf: {avgConfidence.toFixed(1)}%</span>}
            {file && <span>{file.name}</span>}
          </div>
        </div>
      </div>
      {file && activeView === "workspace" && (
        <button onClick={handleProcess} disabled={loading} style={{
          position: "fixed", bottom: 80, left: "50%", transform: "translateX(-50%)",
          padding: "14px 32px", background: "#6366f1", color: "#fff", border: "none",
          borderRadius: 50, cursor: loading ? "not-allowed" : "pointer", fontSize: 15, fontWeight: 600,
          boxShadow: "0 4px 20px rgba(99, 102, 241, 0.4)", transition: "all 0.2s"
        }}>
          {loading ? "Processing..." : "Process Document"}
        </button>
      )}
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
