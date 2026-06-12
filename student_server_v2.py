"""
Student RAG Server v3.1 — Phiên bản với Embedding Model mạnh hơn
MSSV: B22DCVT415

THAY ĐỔI SO VỚI v3.0:
  - Model: intfloat/multilingual-e5-large (thay cho vietnamese-sbert)
  - Dim: 1024 (thay vì 768)
  - E5 prefix: "query: " cho câu hỏi, "passage: " cho tài liệu
  - Batch size giảm (32) do model lớn hơn

Chiến thuật áp dụng (giữ nguyên):
  1. Parent-Child Indexing (Small-to-Big Retrieval)
  2. Hybrid Search: BM25 + Vector + RRF Fusion
  3. MMR (Maximum Marginal Relevance) cho đa dạng context
  4. Document Reordering (Lost in the Middle fix)
  5. Optimized MCQ Prompt với Chain of Thought
  6. Vietnamese Text Preprocessing
  7. LLM Retry + Timeout Management
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Tuple
import uvicorn
import os
import sys
import pickle
import traceback
import time
import math
import re
import unicodedata
import numpy as np

# ============================================================
# CẤU HÌNH
# ============================================================
STUDENT_ID = "B22DCVT415"
TEACHER_PROXY_URL = "http://192.168.50.218:8000/api/v1/proxy"

# ===== THAY ĐỔI CHÍNH: Model embedding mạnh hơn =====
EMBEDDING_MODEL_NAME = "intfloat/multilingual-e5-large"
# E5 models yêu cầu prefix để hoạt động tốt:
#   - "query: " cho câu hỏi/truy vấn
#   - "passage: " cho đoạn văn/tài liệu
E5_QUERY_PREFIX = "query: "
E5_PASSAGE_PREFIX = "passage: "
# ======================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_MODEL_DIR = os.path.join(BASE_DIR, "models", "multilingual-e5-large")
VECTOR_DB_DIR = os.path.join(BASE_DIR, "vector_db_v2")  # Tách riêng DB để không conflict với v1

# Chunking config — Parent-Child
PARENT_CHUNK_SIZE = 1000       # Parent chunks lớn → đưa vào LLM
PARENT_OVERLAP = 200           # Overlap giữa parents
CHILD_CHUNK_SIZE = 300         # Child chunks nhỏ → dùng để search
CHILD_OVERLAP = 50             # Overlap giữa children

# Retrieval config
TOP_K_PER_SYSTEM = 20          # Số kết quả từ mỗi hệ thống (BM25/Vector)
RRF_K = 60                     # Hằng số RRF
MMR_LAMBDA = 0.7               # Cân bằng giữa relevance và diversity
TOP_K_FINAL = 5                # Số chunks cuối cùng đưa vào LLM

# LLM config
LLM_TIMEOUT_FIRST = 25         # Timeout lần gọi đầu
LLM_TIMEOUT_RETRY = 25         # Timeout lần retry
LLM_MODEL = "gpt-4o-mini"
MAX_PROMPT_TOKENS = 3800       # Giới hạn 4K tokens (trừ ~200 cho output)

SERVER_PORT = 5050


# ============================================================
# ERROR DIAGNOSTIC (giữ lại từ v2)
# ============================================================
class ErrorDiagnostic:
    @staticmethod
    def print_error(title, error, suggestion, extra=""):
        print(f"\n{'='*60}")
        print(f"❌ LỖI: {title}")
        print(f"{'='*60}")
        print(f"  Chi tiết: {type(error).__name__}: {error}")
        if extra:
            print(f"  Thêm: {extra}")
        print(f"\n  💡 CÁCH SỬA:")
        for i, line in enumerate(suggestion.strip().split('\n'), 1):
            print(f"     {i}. {line.strip()}")
        print(f"{'='*60}\n")

    @staticmethod
    def check_port(port):
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(('0.0.0.0', port))
            sock.close()
            return True
        except OSError:
            sock.close()
            return False

    @staticmethod
    def check_disk_space(path):
        import shutil
        try:
            total, used, free = shutil.disk_usage(path)
            return free // (1024 * 1024), True
        except Exception:
            return 0, False

    @staticmethod
    def check_dependencies():
        missing = []
        deps = {
            'fastapi': 'fastapi', 'uvicorn': 'uvicorn',
            'sentence_transformers': 'sentence-transformers',
            'faiss': 'faiss-cpu', 'numpy': 'numpy', 'openai': 'openai',
        }
        for module, pip_name in deps.items():
            try:
                __import__(module)
            except ImportError:
                missing.append(pip_name)
        return missing


diag = ErrorDiagnostic()

# --- Kiểm tra dependencies ---
missing_deps = diag.check_dependencies()
if missing_deps:
    print(f"\n❌ Thiếu thư viện: {', '.join(missing_deps)}")
    print(f"💡 Chạy: source .venv/bin/activate && pip install {' '.join(missing_deps)}")
    sys.exit(1)

import faiss
from sentence_transformers import SentenceTransformer
from openai import OpenAI

# --- Kiểm tra port ---
if not diag.check_port(SERVER_PORT):
    print(f"\n❌ Port {SERVER_PORT} đang bị chiếm!")
    print(f"💡 Chạy: lsof -i :{SERVER_PORT} → kill -9 <PID>")
    sys.exit(1)


# ============================================================
# VIETNAMESE TEXT PREPROCESSOR
# ============================================================
class TextPreprocessor:
    """Chuẩn hóa text tiếng Việt trước khi chunking/search."""

    @staticmethod
    def normalize(text: str) -> str:
        """Chuẩn hóa Unicode NFC + clean whitespace."""
        text = unicodedata.normalize('NFC', text)
        text = re.sub(r'\r\n', '\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    @staticmethod
    def tokenize_for_bm25(text: str) -> List[str]:
        """Tokenize đơn giản cho BM25 — lowercase + split."""
        text = text.lower()
        text = unicodedata.normalize('NFC', text)
        # Giữ ký tự chữ cái (bao gồm tiếng Việt), số, bỏ dấu câu
        tokens = re.findall(r'[a-zA-ZÀ-ỹ0-9]+', text)
        # Loại bỏ stopwords phổ biến tiếng Việt
        stopwords = {
            'là', 'và', 'của', 'có', 'được', 'cho', 'các', 'trong',
            'với', 'này', 'đã', 'để', 'từ', 'theo', 'về', 'khi',
            'đó', 'một', 'không', 'những', 'cũng', 'như', 'hay',
            'hoặc', 'nếu', 'thì', 'mà', 'do', 'vì', 'bởi', 'tại',
            'ra', 'đến', 'lên', 'vào', 'bị', 'tới', 'trên', 'dưới',
            'nên', 'sẽ', 'đang', 'rất', 'còn', 'nhưng', 'hơn',
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'of',
            'in', 'to', 'for', 'and', 'or', 'but', 'at', 'by',
            'on', 'with', 'as', 'it', 'be', 'this', 'that',
        }
        return [t for t in tokens if t not in stopwords and len(t) > 1]


# ============================================================
# SEMANTIC CHUNKER — Parent-Child Indexing
# ============================================================
class SemanticChunker:
    """
    Recursive chunking: tạo Parent chunks (lớn) và Child chunks (nhỏ).
    - Child chunks nhỏ → dùng để search (chính xác cao)
    - Parent chunks lớn → đưa vào LLM (đủ context)
    """

    def __init__(
        self,
        parent_size: int = PARENT_CHUNK_SIZE,
        parent_overlap: int = PARENT_OVERLAP,
        child_size: int = CHILD_CHUNK_SIZE,
        child_overlap: int = CHILD_OVERLAP,
    ):
        self.parent_size = parent_size
        self.parent_overlap = parent_overlap
        self.child_size = child_size
        self.child_overlap = child_overlap

    def _split_at_boundary(self, text: str, target_size: int, overlap: int) -> List[str]:
        """Cắt text tại ranh giới câu/đoạn, có overlap."""
        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = start + target_size

            if end < text_len:
                # Tìm điểm cắt tốt nhất (ranh giới câu/đoạn)
                search_start = max(start + target_size // 2, start)
                best_break = -1
                for sep in ['\n\n', '.\n', '. ', '?\n', '? ', '!\n', '! ', '\n', '; ', ', ']:
                    pos = text.rfind(sep, search_start, end + 50)
                    if pos > best_break:
                        best_break = pos + len(sep)
                if best_break > start:
                    end = best_break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - overlap if end < text_len else text_len

        return chunks

    def chunk(self, text: str) -> Tuple[List[str], List[str], List[int]]:
        """
        Tạo parent và child chunks.
        Returns:
            parent_chunks: List[str] — chunks lớn cho LLM context
            child_chunks: List[str] — chunks nhỏ cho search
            child_to_parent: List[int] — mapping child_idx → parent_idx
        """
        text = TextPreprocessor.normalize(text)

        if not text:
            return [], [], []

        # 1. Tạo parent chunks
        parent_chunks = self._split_at_boundary(text, self.parent_size, self.parent_overlap)

        # 2. Tạo child chunks từ mỗi parent
        child_chunks = []
        child_to_parent = []

        for parent_idx, parent in enumerate(parent_chunks):
            children = self._split_at_boundary(parent, self.child_size, self.child_overlap)
            for child in children:
                child_chunks.append(child)
                child_to_parent.append(parent_idx)

        return parent_chunks, child_chunks, child_to_parent


# ============================================================
# BM25 RETRIEVER — Okapi BM25 Custom Implementation
# ============================================================
class BM25Retriever:
    """
    Okapi BM25 cho keyword search.
    Không cần thêm dependency — tự implement.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_freqs: Dict[str, int] = {}   # term → số doc chứa term
        self.doc_lens: List[int] = []          # length mỗi doc
        self.avgdl: float = 0                  # avg doc length
        self.n_docs: int = 0
        self.tokenized_docs: List[List[str]] = []
        self.idf: Dict[str, float] = {}

    def fit(self, documents: List[str]):
        """Build BM25 index từ danh sách documents."""
        self.tokenized_docs = [TextPreprocessor.tokenize_for_bm25(doc) for doc in documents]
        self.n_docs = len(self.tokenized_docs)
        self.doc_lens = [len(doc) for doc in self.tokenized_docs]
        self.avgdl = sum(self.doc_lens) / max(self.n_docs, 1)

        # Tính document frequency
        self.doc_freqs = {}
        for doc_tokens in self.tokenized_docs:
            unique_tokens = set(doc_tokens)
            for token in unique_tokens:
                self.doc_freqs[token] = self.doc_freqs.get(token, 0) + 1

        # Tính IDF
        self.idf = {}
        for term, df in self.doc_freqs.items():
            # IDF with smoothing (BM25 variant)
            self.idf[term] = math.log((self.n_docs - df + 0.5) / (df + 0.5) + 1.0)

    def score(self, query: str, top_k: int = 20) -> List[Tuple[int, float]]:
        """
        Tính BM25 score cho query.
        Returns: List[(doc_index, score)] sorted by score desc.
        """
        query_tokens = TextPreprocessor.tokenize_for_bm25(query)
        scores = []

        for doc_idx, doc_tokens in enumerate(self.tokenized_docs):
            doc_score = 0.0
            doc_len = self.doc_lens[doc_idx]

            # Đếm term frequency trong doc
            tf_dict = {}
            for token in doc_tokens:
                tf_dict[token] = tf_dict.get(token, 0) + 1

            for q_term in query_tokens:
                if q_term not in self.idf:
                    continue
                tf = tf_dict.get(q_term, 0)
                if tf == 0:
                    continue
                idf = self.idf[q_term]
                # Okapi BM25 formula
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / max(self.avgdl, 1))
                doc_score += idf * (numerator / denominator)

            scores.append((doc_idx, doc_score))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def get_state(self) -> dict:
        """Serialize BM25 state để lưu disk."""
        return {
            'k1': self.k1, 'b': self.b,
            'doc_freqs': self.doc_freqs,
            'doc_lens': self.doc_lens,
            'avgdl': self.avgdl,
            'n_docs': self.n_docs,
            'tokenized_docs': self.tokenized_docs,
            'idf': self.idf,
        }

    def load_state(self, state: dict):
        """Load BM25 state từ disk."""
        self.k1 = state['k1']
        self.b = state['b']
        self.doc_freqs = state['doc_freqs']
        self.doc_lens = state['doc_lens']
        self.avgdl = state['avgdl']
        self.n_docs = state['n_docs']
        self.tokenized_docs = state['tokenized_docs']
        self.idf = state['idf']


# ============================================================
# HYBRID RETRIEVER — BM25 + Vector + RRF + MMR
# ============================================================
class HybridRetriever:
    """
    Kết hợp BM25 (keyword) + FAISS (semantic) + RRF fusion + MMR diversity.
    """

    @staticmethod
    def rrf_fusion(
        vector_results: List[Tuple[int, float]],
        bm25_results: List[Tuple[int, float]],
        k: int = RRF_K
    ) -> List[Tuple[int, float]]:
        """
        Reciprocal Rank Fusion: hợp nhất 2 ranked lists.
        score(d) = 1/(k + rank_vector(d)) + 1/(k + rank_bm25(d))
        """
        rrf_scores: Dict[int, float] = {}

        for rank, (doc_idx, _) in enumerate(vector_results):
            rrf_scores[doc_idx] = rrf_scores.get(doc_idx, 0) + 1.0 / (k + rank + 1)

        for rank, (doc_idx, _) in enumerate(bm25_results):
            rrf_scores[doc_idx] = rrf_scores.get(doc_idx, 0) + 1.0 / (k + rank + 1)

        # Sort by RRF score
        results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        return results

    @staticmethod
    def mmr_select(
        query_embedding: np.ndarray,
        candidate_indices: List[int],
        all_embeddings: np.ndarray,
        top_k: int = TOP_K_FINAL,
        lambda_param: float = MMR_LAMBDA
    ) -> List[int]:
        """
        Maximum Marginal Relevance: chọn chunks vừa liên quan vừa đa dạng.
        MMR = λ·sim(q,d) - (1-λ)·max(sim(d, d_selected))
        """
        if len(candidate_indices) <= top_k:
            return candidate_indices

        # Normalize query
        query_norm = query_embedding.copy()
        norm = np.linalg.norm(query_norm)
        if norm > 0:
            query_norm = query_norm / norm

        # Compute similarity with query for all candidates
        candidate_embeddings = all_embeddings[candidate_indices]
        norms = np.linalg.norm(candidate_embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        candidate_embeddings_norm = candidate_embeddings / norms

        query_sims = candidate_embeddings_norm @ query_norm.flatten()

        selected = []
        remaining = list(range(len(candidate_indices)))

        for _ in range(top_k):
            if not remaining:
                break

            best_idx = -1
            best_score = -float('inf')

            for i in remaining:
                relevance = query_sims[i]

                # Max similarity with already selected
                if selected:
                    selected_embeddings = candidate_embeddings_norm[selected]
                    diversity_penalties = selected_embeddings @ candidate_embeddings_norm[i]
                    max_sim_selected = float(np.max(diversity_penalties))
                else:
                    max_sim_selected = 0.0

                mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim_selected

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = i

            if best_idx >= 0:
                selected.append(best_idx)
                remaining.remove(best_idx)

        return [candidate_indices[i] for i in selected]


# ============================================================
# DOCUMENT REORDERER — Lost in the Middle fix
# ============================================================
class DocumentReorderer:
    """
    Sắp xếp lại chunks để chống Lost in the Middle.
    LLM nhớ tốt thông tin ở ĐẦU và CUỐI prompt.
    Pattern: [rank 1, rank 3, rank 5, ..., rank 4, rank 2]
    """

    @staticmethod
    def reorder(chunks: List[str]) -> List[str]:
        if len(chunks) <= 2:
            return chunks

        reordered = []
        # Vị trí lẻ (1, 3, 5...) → đầu
        for i in range(0, len(chunks), 2):
            reordered.append(chunks[i])
        # Vị trí chẵn (2, 4, 6...) → cuối (đảo ngược)
        even_positions = [chunks[i] for i in range(1, len(chunks), 2)]
        reordered.extend(reversed(even_positions))

        return reordered


# ============================================================
# PROMPT BUILDER — MCQ Optimized with CoT
# ============================================================
class PromptBuilder:
    """Xây dựng prompt tối ưu cho câu hỏi trắc nghiệm, có giới hạn 4K tokens."""

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Ước lượng số tokens (~4 ký tự/token cho tiếng Việt mixed)."""
        return len(text) // 4 + 1

    @staticmethod
    def build_mcq_prompt(question: str, context_chunks: List[str]) -> str:
        # Template cố định (không có context) ≈ ~200 tokens
        template_overhead = 200
        question_tokens = PromptBuilder.estimate_tokens(question)
        available_for_context = MAX_PROMPT_TOKENS - template_overhead - question_tokens

        # Truncate context chunks nếu vượt giới hạn
        if context_chunks and available_for_context > 0:
            selected_chunks = []
            current_tokens = 0
            for chunk in context_chunks:
                chunk_tokens = PromptBuilder.estimate_tokens(chunk) + 3  # +3 cho separator "\n---\n"
                if current_tokens + chunk_tokens > available_for_context:
                    # Cắt chunk cuối nếu còn chỗ
                    remaining = available_for_context - current_tokens
                    if remaining > 50:  # Chỉ thêm nếu còn >= 50 tokens
                        truncated = chunk[:remaining * 4]
                        selected_chunks.append(truncated + "...")
                        print(f"[Prompt] ⚠️ Truncated chunk ({chunk_tokens}→{remaining} tokens) để giữ trong 4K")
                    break
                selected_chunks.append(chunk)
                current_tokens += chunk_tokens

            if len(selected_chunks) < len(context_chunks):
                print(f"[Prompt] ⚠️ Giới hạn 4K tokens: dùng {len(selected_chunks)}/{len(context_chunks)} chunks")

            context_text = "\n---\n".join(selected_chunks) if selected_chunks else "(Không có ngữ cảnh)"
        else:
            context_text = "\n---\n".join(context_chunks) if context_chunks else "(Không có ngữ cảnh)"

        prompt = f"""Bạn là một chuyên gia trả lời câu hỏi trắc nghiệm. Hãy phân tích kỹ ngữ cảnh được cung cấp.

=== NGỮ CẢNH TỪ TÀI LIỆU ===
{context_text}
=== HẾT NGỮ CẢNH ===

HƯỚNG DẪN:
1. Đọc kỹ ngữ cảnh ở trên
2. Xác định thông tin liên quan đến câu hỏi
3. So sánh từng đáp án A, B, C, D với thông tin trong ngữ cảnh
4. Chọn đáp án đúng nhất dựa trên ngữ cảnh
5. Nếu ngữ cảnh không đủ thông tin, chọn đáp án hợp lý nhất dựa trên kiến thức chung

QUY ĐỊNH: CHỈ TRẢ VỀ ĐÚNG 1 KÝ TỰ (A, B, C hoặc D). KHÔNG giải thích.

Câu hỏi: {question}

Đáp án:"""

        total_tokens = PromptBuilder.estimate_tokens(prompt)
        print(f"[Prompt] 📊 Estimated tokens: {total_tokens}/{MAX_PROMPT_TOKENS}")

        return prompt


# ============================================================
# VECTOR STORE v3.1 — Parent-Child + Persistence (E5 Compatible)
# ============================================================
class VectorStore:
    """
    FAISS Vector Store với Parent-Child indexing.
    - Index child chunks (nhỏ, chính xác)
    - Trả parent chunks (lớn, đủ context)
    """

    def __init__(self, dim: int, db_dir: str):
        self.dim = dim
        self.db_dir = db_dir
        self.index_path = os.path.join(db_dir, "index.faiss")
        self.data_path = os.path.join(db_dir, "data.pkl")

        self.index: faiss.IndexFlatIP = None
        self.child_chunks: List[str] = []
        self.parent_chunks: List[str] = []
        self.child_to_parent: List[int] = []
        self.child_embeddings: np.ndarray = None  # Lưu để dùng cho MMR
        self.bm25 = BM25Retriever()

        self._load_or_create()

    def _load_or_create(self):
        if os.path.exists(self.index_path) and os.path.exists(self.data_path):
            try:
                print(f"[VectorStore] Loading vector DB từ: {self.db_dir}")
                self.index = faiss.read_index(self.index_path)

                with open(self.data_path, "rb") as f:
                    data = pickle.load(f)

                self.child_chunks = data.get('child_chunks', [])
                self.parent_chunks = data.get('parent_chunks', [])
                self.child_to_parent = data.get('child_to_parent', [])
                self.child_embeddings = data.get('child_embeddings', None)

                # Load BM25 state
                bm25_state = data.get('bm25_state', None)
                if bm25_state:
                    self.bm25.load_state(bm25_state)

                # Validate
                if self.index.ntotal != len(self.child_chunks):
                    print(f"[VectorStore] ⚠️ Index/chunks mismatch. Tạo mới...")
                    self._create_new()
                    return

                print(f"[VectorStore] ✅ Loaded: {len(self.child_chunks)} children, {len(self.parent_chunks)} parents")

            except Exception as e:
                print(f"[VectorStore] ⚠️ Lỗi load: {e}. Tạo mới...")
                self._create_new()
        else:
            print(f"[VectorStore] Tạo vector DB mới")
            self._create_new()

    def _create_new(self):
        self.index = faiss.IndexFlatIP(self.dim)
        self.child_chunks = []
        self.parent_chunks = []
        self.child_to_parent = []
        self.child_embeddings = None
        self.bm25 = BM25Retriever()

    def add(self, parent_chunks: List[str], child_chunks: List[str],
            child_to_parent: List[int], child_embeddings: np.ndarray):
        """Thêm parent-child data vào store."""
        faiss.normalize_L2(child_embeddings)

        self.index.add(child_embeddings)
        self.parent_chunks.extend(parent_chunks)

        # Offset child_to_parent indices
        parent_offset = len(self.parent_chunks) - len(parent_chunks)
        adjusted_mapping = [idx + parent_offset for idx in child_to_parent]

        self.child_chunks.extend(child_chunks)
        self.child_to_parent.extend(adjusted_mapping)

        # Lưu embeddings cho MMR
        if self.child_embeddings is None:
            self.child_embeddings = child_embeddings.copy()
        else:
            self.child_embeddings = np.vstack([self.child_embeddings, child_embeddings])

        # Build BM25 index
        self.bm25.fit(self.child_chunks)

        print(f"[VectorStore] ✅ Added {len(child_chunks)} children, {len(parent_chunks)} parents")
        print(f"[VectorStore]    Total: {len(self.child_chunks)} children, {len(self.parent_chunks)} parents")

    def hybrid_search(self, query: str, query_embedding: np.ndarray,
                      top_k: int = TOP_K_FINAL) -> List[str]:
        """
        Hybrid search: Vector + BM25 → RRF → MMR → Parent lookup → Reorder
        Returns: List[str] — parent chunks sẵn sàng đưa vào LLM
        """
        if self.index.ntotal == 0:
            print("[VectorStore] ⚠️ Vector DB trống!")
            return []

        n_search = min(TOP_K_PER_SYSTEM, self.index.ntotal)

        # 1. Vector Search (FAISS)
        query_emb = query_embedding.copy()
        faiss.normalize_L2(query_emb)
        scores, indices = self.index.search(query_emb, n_search)
        vector_results = [(int(idx), float(score)) for idx, score in zip(indices[0], scores[0]) if idx >= 0]

        # 2. BM25 Search
        bm25_results = self.bm25.score(query, top_k=n_search)

        # 3. RRF Fusion
        rrf_results = HybridRetriever.rrf_fusion(vector_results, bm25_results)

        # 4. MMR Selection (chọn top candidates đa dạng)
        candidate_indices = [idx for idx, _ in rrf_results[:TOP_K_PER_SYSTEM]]

        if self.child_embeddings is not None and len(candidate_indices) > top_k:
            selected_indices = HybridRetriever.mmr_select(
                query_embedding, candidate_indices,
                self.child_embeddings, top_k=top_k
            )
        else:
            selected_indices = candidate_indices[:top_k]

        # 5. Child → Parent mapping (deduplicate)
        seen_parents = set()
        parent_results = []
        for child_idx in selected_indices:
            if child_idx < len(self.child_to_parent):
                parent_idx = self.child_to_parent[child_idx]
                if parent_idx not in seen_parents and parent_idx < len(self.parent_chunks):
                    seen_parents.add(parent_idx)
                    parent_results.append(self.parent_chunks[parent_idx])

        # 6. Document Reordering (Lost in the Middle)
        parent_results = DocumentReorderer.reorder(parent_results)

        print(f"[Search] Vector:{len(vector_results)} → BM25:{len(bm25_results)} → RRF:{len(rrf_results)} → MMR:{len(selected_indices)} → Parents:{len(parent_results)}")

        return parent_results

    def save(self):
        try:
            os.makedirs(self.db_dir, exist_ok=True)
            faiss.write_index(self.index, self.index_path)
            with open(self.data_path, "wb") as f:
                pickle.dump({
                    'child_chunks': self.child_chunks,
                    'parent_chunks': self.parent_chunks,
                    'child_to_parent': self.child_to_parent,
                    'child_embeddings': self.child_embeddings,
                    'bm25_state': self.bm25.get_state(),
                }, f)
            print(f"[VectorStore] ✅ Saved to disk ({len(self.child_chunks)} children, {len(self.parent_chunks)} parents)")
        except Exception as e:
            diag.print_error("Lỗi ghi Vector DB", e, f"Kiểm tra disk: df -h .\nChạy: chmod -R 755 {self.db_dir}")

    def clear(self):
        self._create_new()

    @property
    def is_loaded(self) -> bool:
        return self.index.ntotal > 0


# ============================================================
# KHỞI TẠO
# ============================================================
app = FastAPI(title="Student RAG Server v3.1 (E5-Large)", version="3.1")

print("=" * 60)
print(f"[INIT] Student RAG Server v3.1 — MSSV: {STUDENT_ID}")
print(f"[INIT] 🔥 Model NÂNG CẤP: {EMBEDDING_MODEL_NAME}")
print(f"[INIT] Chiến thuật: Parent-Child + BM25+Vector+RRF + MMR + Reorder + CoT")
print(f"[INIT] Loading embedding model: {EMBEDDING_MODEL_NAME}")

# Load model
embedding_model = None
try:
    if os.path.exists(LOCAL_MODEL_DIR):
        print(f"[INIT] Model local: {LOCAL_MODEL_DIR}")
        embedding_model = SentenceTransformer(LOCAL_MODEL_DIR)
    else:
        print(f"[INIT] ⬇️ Tải model từ HuggingFace (E5-Large ~1.2GB, có thể mất vài phút)...")
        embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        os.makedirs(LOCAL_MODEL_DIR, exist_ok=True)
        embedding_model.save(LOCAL_MODEL_DIR)
        print(f"[INIT] ✅ Đã lưu model vào {LOCAL_MODEL_DIR}")
except Exception as e:
    diag.print_error("Không load được model", e,
                     f"Xóa & tải lại: rm -rf {LOCAL_MODEL_DIR}\n"
                     f"Hoặc tải thủ công:\n"
                     f"  python3 -c \"from sentence_transformers import SentenceTransformer; "
                     f"m = SentenceTransformer('{EMBEDDING_MODEL_NAME}'); "
                     f"m.save('{LOCAL_MODEL_DIR}')\"")
    sys.exit(1)

EMBEDDING_DIM = embedding_model.get_embedding_dimension()
print(f"[INIT] ✅ Model loaded! Dim={EMBEDDING_DIM}")
print(f"[INIT] ℹ️ So sánh: vietnamese-sbert=768d → E5-Large={EMBEDDING_DIM}d")

# Pre-warm model (giảm latency câu hỏi đầu tiên)
# E5 cần prefix ngay cả khi warm up
print(f"[INIT] Pre-warming model...")
_ = embedding_model.encode([f"{E5_QUERY_PREFIX}warm up"], convert_to_numpy=True)
print(f"[INIT] ✅ Model warmed up!")

# Khởi tạo chunker & store
chunker = SemanticChunker()
vector_store = VectorStore(dim=EMBEDDING_DIM, db_dir=VECTOR_DB_DIR)
print(f"[INIT] ✅ Vector DB: {'Loaded' if vector_store.is_loaded else 'Empty'}")
print(f"[INIT] ⚠️ DB path: {VECTOR_DB_DIR} (tách riêng với v1)")
print("=" * 60)


# ============================================================
# SCHEMAS
# ============================================================
class UploadRequest(BaseModel):
    doc_id: Optional[str] = None
    text: str

class UploadResponse(BaseModel):
    status: str
    doc_id: Optional[str] = None
    chunks: int

class AskRequest(BaseModel):
    question: str

class AskResponse(BaseModel):
    answer: str
    sources: List[str] = []


# ============================================================
# GLOBAL EXCEPTION HANDLER
# ============================================================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"\n❌ UNHANDLED: {request.method} {request.url.path} → {type(exc).__name__}: {exc}")
    traceback.print_exc()
    return JSONResponse(status_code=500, content={"status": "error", "error": str(exc)})


# ============================================================
# API ENDPOINTS
# ============================================================
@app.post("/upload", response_model=UploadResponse)
async def upload_document(req: UploadRequest):
    global vector_store
    doc_id = req.doc_id or "default_doc"
    start_time = time.time()

    print(f"\n{'='*60}")
    print(f"[UPLOAD] 📥 doc_id={doc_id}, length={len(req.text)} chars")

    if not req.text or not req.text.strip():
        print(f"[UPLOAD] ❌ Text rỗng!")
        return UploadResponse(status="error", doc_id=doc_id, chunks=0)

    try:
        # 1. Parent-Child Chunking
        parent_chunks, child_chunks, child_to_parent = chunker.chunk(req.text)
        print(f"[UPLOAD] ✅ 1/3 Chunking: {len(parent_chunks)} parents, {len(child_chunks)} children")

        if not child_chunks:
            print(f"[UPLOAD] ❌ Không tạo được chunk nào!")
            return UploadResponse(status="error", doc_id=doc_id, chunks=0)

        # 2. Embedding child chunks — THÊM E5 PREFIX "passage: "
        print(f"[UPLOAD] ⏳ 2/3 Embedding {len(child_chunks)} children với E5 prefix...")
        prefixed_chunks = [f"{E5_PASSAGE_PREFIX}{chunk}" for chunk in child_chunks]
        child_embeddings = embedding_model.encode(
            prefixed_chunks, show_progress_bar=True,
            convert_to_numpy=True, batch_size=32  # Giảm batch_size vì model lớn hơn
        ).astype(np.float32)
        print(f"[UPLOAD] ✅ 2/3 Embedding done. Shape: {child_embeddings.shape}")

        # 3. Add to VectorStore + BM25 + Save
        vector_store.add(parent_chunks, child_chunks, child_to_parent, child_embeddings)
        vector_store.save()

        elapsed = time.time() - start_time
        print(f"[UPLOAD] 🎉 DONE! ({elapsed:.1f}s) {len(parent_chunks)}P + {len(child_chunks)}C")

        return UploadResponse(status="success", doc_id=doc_id, chunks=len(child_chunks))

    except Exception as e:
        print(f"[UPLOAD] ❌ {type(e).__name__}: {e}")
        traceback.print_exc()
        return UploadResponse(status="error", doc_id=doc_id, chunks=0)


@app.post("/ask", response_model=AskResponse)
async def ask_question(req: AskRequest):
    start_time = time.time()
    print(f"\n[ASK] 📝 {req.question[:100]}...")

    if not req.question or not req.question.strip():
        return AskResponse(answer="A", sources=[])

    # 1. Hybrid Search (Vector + BM25 + RRF + MMR + Reorder)
    #    THÊM E5 PREFIX "query: " cho câu hỏi
    try:
        prefixed_query = f"{E5_QUERY_PREFIX}{req.question}"
        query_embedding = embedding_model.encode(
            [prefixed_query], convert_to_numpy=True
        ).astype(np.float32)
        sources = vector_store.hybrid_search(req.question, query_embedding, top_k=TOP_K_FINAL)
    except Exception as e:
        print(f"[ASK] ❌ Search error: {e}")
        sources = []

    # 2. Build MCQ prompt with CoT
    prompt = PromptBuilder.build_mcq_prompt(req.question, sources)

    # 3. Gọi LLM với retry
    final_answer = 'A'
    client = OpenAI(base_url=TEACHER_PROXY_URL, api_key=STUDENT_ID)

    for attempt, timeout in enumerate([LLM_TIMEOUT_FIRST, LLM_TIMEOUT_RETRY], 1):
        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=5,
                timeout=timeout
            )
            answer = response.choices[0].message.content.strip().upper()

            # Parse: tìm ký tự A/B/C/D đầu tiên
            valid = ['A', 'B', 'C', 'D']
            for char in answer:
                if char in valid:
                    final_answer = char
                    break

            elapsed = time.time() - start_time
            print(f"[ASK] ✅ Đáp án: {final_answer} (raw: '{answer}') [{elapsed:.1f}s, attempt {attempt}]")
            break  # Thành công → thoát retry loop

        except Exception as e:
            elapsed = time.time() - start_time
            error_name = type(e).__name__

            if attempt == 1:
                print(f"[ASK] ⚠️ Attempt 1 failed ({error_name}), retrying... [{elapsed:.1f}s]")
                continue
            else:
                print(f"[ASK] ❌ Attempt 2 failed ({error_name}: {e}) [{elapsed:.1f}s]")
                # Phân tích lỗi
                if "Connection" in error_name:
                    print(f"[ASK] 💡 Kiểm tra WiFi ASUS_E0")
                elif "Timeout" in error_name or "timeout" in str(e).lower():
                    print(f"[ASK] 💡 Proxy quá tải")
                elif "401" in str(e):
                    print(f"[ASK] 💡 Sai MSSV/API key: {STUDENT_ID}")
                print(f"[ASK] ⚠️ Trả mặc định: {final_answer}")

    return AskResponse(answer=final_answer, sources=sources)


# ============================================================
# HEALTH & DEBUG
# ============================================================
@app.get("/")
async def health():
    free_mb, _ = diag.check_disk_space(BASE_DIR)
    return {
        "status": "running",
        "version": "3.1-e5-large",
        "student_id": STUDENT_ID,
        "embedding_model": EMBEDDING_MODEL_NAME,
        "embedding_dim": EMBEDDING_DIM,
        "strategies": ["Parent-Child", "BM25+Vector+RRF", "MMR", "Reorder", "CoT", "E5-Prefix"],
        "vector_db_loaded": vector_store.is_loaded,
        "parent_chunks": len(vector_store.parent_chunks),
        "child_chunks": len(vector_store.child_chunks),
        "total_chunks": len(vector_store.child_chunks),
        "disk_free_mb": free_mb,
    }


@app.get("/debug")
async def debug():
    return {
        "student_id": STUDENT_ID,
        "model_info": {
            "name": EMBEDDING_MODEL_NAME,
            "dim": EMBEDDING_DIM,
            "query_prefix": E5_QUERY_PREFIX,
            "passage_prefix": E5_PASSAGE_PREFIX,
            "local_path": LOCAL_MODEL_DIR,
        },
        "config": {
            "parent_chunk_size": PARENT_CHUNK_SIZE,
            "parent_overlap": PARENT_OVERLAP,
            "child_chunk_size": CHILD_CHUNK_SIZE,
            "child_overlap": CHILD_OVERLAP,
            "top_k_per_system": TOP_K_PER_SYSTEM,
            "rrf_k": RRF_K,
            "mmr_lambda": MMR_LAMBDA,
            "top_k_final": TOP_K_FINAL,
            "llm_model": LLM_MODEL,
            "llm_timeout": [LLM_TIMEOUT_FIRST, LLM_TIMEOUT_RETRY],
        },
        "vector_db": {
            "loaded": vector_store.is_loaded,
            "db_dir": VECTOR_DB_DIR,
            "parent_chunks": len(vector_store.parent_chunks),
            "child_chunks": len(vector_store.child_chunks),
            "index_size": vector_store.index.ntotal if vector_store.index else 0,
        },
        "bm25": {
            "n_docs": vector_store.bm25.n_docs,
            "vocab_size": len(vector_store.bm25.idf),
        },
        "sample_parents": vector_store.parent_chunks[:2] if vector_store.parent_chunks else [],
        "sample_children": vector_store.child_chunks[:3] if vector_store.child_chunks else [],
    }


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"  🚀 STUDENT RAG SERVER v3.1 — E5-LARGE EDITION")
    print(f"  📌 MSSV: {STUDENT_ID}")
    print(f"  🧠 Model: {EMBEDDING_MODEL_NAME} (dim={EMBEDDING_DIM})")
    print(f"  📦 DB: {'✅ ' + str(len(vector_store.child_chunks)) + 'C/' + str(len(vector_store.parent_chunks)) + 'P' if vector_store.is_loaded else '⬜ Trống'}")
    print(f"  ⚡ Strategies: Parent-Child | BM25+Vector+RRF | MMR | Reorder | CoT | E5-Prefix")
    print(f"  🌐 Port: {SERVER_PORT}")
    print(f"{'='*60}\n")
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)
