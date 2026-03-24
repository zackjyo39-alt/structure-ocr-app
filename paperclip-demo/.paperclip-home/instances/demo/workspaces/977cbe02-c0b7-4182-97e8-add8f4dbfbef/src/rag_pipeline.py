"""Automotive RAG Pipeline.

Provides PDF ingestion, chunking, embedding, vector retrieval,
and LLM-augmented answering for automotive technical documents.
"""

import re
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Any, Optional


# ---------------------------------------------------------------------------
# 1. PDF Parsing
# ---------------------------------------------------------------------------

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract raw text from a PDF file using PyMuPDF (fitz).

    Falls back to a minimal stub if PyMuPDF is not installed so the
    rest of the pipeline can be tested without the dependency.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise RuntimeError(
            "PyMuPDF is required for PDF parsing. "
            "Install with: pip install PyMuPDF"
        )

    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(str(path))
    pages = []
    for page in doc:
        text = page.get_text("text")
        if text:
            pages.append(text)
    doc.close()
    return "\n".join(pages)


def normalize_whitespace(text: str) -> str:
    """Collapse runs of whitespace and strip leading/trailing space."""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# 2. Chunking
# ---------------------------------------------------------------------------

def chunk_text(
    text: str,
    chunk_size: int = 512,
    overlap: int = 64,
) -> List[Dict[str, Any]]:
    """Split text into overlapping chunks.

    Each chunk is a dict with keys:
      - text: str
      - index: int
      - hash: str (content-addressable id)
    """
    words = text.split()
    if not words:
        return []

    chunks = []
    step = max(1, chunk_size - overlap)
    for i, start in enumerate(range(0, len(words), step)):
        slice_words = words[start : start + chunk_size]
        chunk_text_str = " ".join(slice_words)
        chunks.append(
            {
                "text": chunk_text_str,
                "index": i,
                "hash": hashlib.sha256(chunk_text_str.encode()).hexdigest()[:16],
            }
        )
    return chunks


# ---------------------------------------------------------------------------
# 3. Embedding (pluggable backend)
# ---------------------------------------------------------------------------

class BaseEmbeddingBackend:
    """Interface for embedding backends."""

    def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError


class HashEmbeddingBackend(BaseEmbeddingBackend):
    """Deterministic hash-based embedding for testing / offline use.

    Produces a fixed-dimension vector by hashing tokens.
    """

    def __init__(self, dim: int = 384):
        self.dim = dim

    def embed(self, texts: List[str]) -> List[List[float]]:
        vectors = []
        for text in texts:
            vec = [0.0] * self.dim
            tokens = re.findall(r"\w+", text.lower())
            for tok in tokens:
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                vec[h % self.dim] += 1.0
            # L2-normalize
            norm = sum(v * v for v in vec) ** 0.5
            if norm > 0:
                vec = [v / norm for v in vec]
            vectors.append(vec)
        return vectors


# ---------------------------------------------------------------------------
# 4. Vector Store
# ---------------------------------------------------------------------------

class InMemoryVectorStore:
    """Simple in-memory vector store with cosine similarity search."""

    def __init__(self):
        self._vectors: List[List[float]] = []
        self._metadatas: List[Dict[str, Any]] = []

    def add(self, vectors: List[List[float]], metadatas: List[Dict[str, Any]]):
        if len(vectors) != len(metadatas):
            raise ValueError("vectors and metadatas must have same length")
        self._vectors.extend(vectors)
        self._metadatas.extend(metadatas)

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def search(self, query_vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        scored = []
        for i, vec in enumerate(self._vectors):
            sim = self._cosine_similarity(query_vector, vec)
            scored.append({"score": sim, "metadata": self._metadatas[i]})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]


# ---------------------------------------------------------------------------
# 5. Prompt Construction & LLM Stub
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are an automotive engineering assistant. "
    "Answer the user's question using only the provided context. "
    "If the answer is not in the context, say so."
)


def build_context(results: List[Dict[str, Any]]) -> str:
    """Join retrieved chunks into a context block."""
    parts = []
    for r in results:
        meta = r["metadata"]
        text = meta.get("text", "")
        parts.append(f"[chunk {meta.get('index', '?')}]\n{text}")
    return "\n\n".join(parts)


def build_prompt(question: str, context: str) -> str:
    """Construct the final prompt for the LLM."""
    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"--- Context ---\n{context}\n"
        f"--- End Context ---\n\n"
        f"Question: {question}\nAnswer:"
    )


def generate_answer(prompt: str) -> str:
    """Generate an answer.

    Replace this stub with a real LLM call (OpenAI, local model, etc.).
    Returns the prompt echo for testing.
    """
    return f"[LLM STUB] Prompt received ({len(prompt)} chars). Replace generate_answer() with a real backend."


# ---------------------------------------------------------------------------
# 6. High-Level Pipeline
# ---------------------------------------------------------------------------

class AutomotiveRAGPipeline:
    """End-to-end RAG pipeline for automotive documents."""

    def __init__(
        self,
        embedding_backend: Optional[BaseEmbeddingBackend] = None,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
    ):
        self.embedding_backend = embedding_backend or HashEmbeddingBackend()
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.vector_store = InMemoryVectorStore()

    def ingest_pdf(self, pdf_path: str) -> int:
        """Ingest a PDF, chunk it, embed, and store.

        Returns the number of chunks added.
        """
        raw = extract_text_from_pdf(pdf_path)
        text = normalize_whitespace(raw)
        chunks = chunk_text(text, self.chunk_size, self.chunk_overlap)
        if not chunks:
            return 0
        texts = [c["text"] for c in chunks]
        vectors = self.embedding_backend.embed(texts)
        self.vector_store.add(vectors, chunks)
        return len(chunks)

    def query(self, question: str, top_k: int = 5) -> str:
        """Retrieve relevant chunks and generate an answer."""
        q_vec = self.embedding_backend.embed([question])[0]
        results = self.vector_store.search(q_vec, top_k=top_k)
        context = build_context(results)
        prompt = build_prompt(question, context)
        return generate_answer(prompt)

    def ingest_text(self, text: str) -> int:
        """Directly ingest plain text (useful for testing)."""
        text = normalize_whitespace(text)
        chunks = chunk_text(text, self.chunk_size, self.chunk_overlap)
        if not chunks:
            return 0
        texts = [c["text"] for c in chunks]
        vectors = self.embedding_backend.embed(texts)
        self.vector_store.add(vectors, chunks)
        return len(chunks)


# ---------------------------------------------------------------------------
# 7. CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    """Quick demo: ingest a PDF (if provided) and answer a sample question."""
    import argparse

    parser = argparse.ArgumentParser(description="Automotive RAG Pipeline")
    parser.add_argument("--pdf", help="Path to PDF to ingest")
    parser.add_argument("--query", default="What is the engine torque spec?", help="Question to ask")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    pipe = AutomotiveRAGPipeline()

    if args.pdf:
        n = pipe.ingest_pdf(args.pdf)
        print(f"Ingested {n} chunks from {args.pdf}")
    else:
        # ingest a small demo corpus
        demo = (
            "The 2024 Model-X engine produces 250 HP at 5500 RPM. "
            "The torque specification is 280 Nm at 4000 RPM. "
            "Oil capacity is 5.2 liters with 5W-30 synthetic."
        )
        n = pipe.ingest_text(demo)
        print(f"Ingested {n} demo chunks")

    answer = pipe.query(args.query, top_k=args.top_k)
    print(f"\nQ: {args.query}\nA: {answer}")


if __name__ == "__main__":
    main()
