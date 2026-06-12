from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, List
import uvicorn
from openai import OpenAI

app = FastAPI()

# Biến global để lưu trữ các chunk của tài liệu (Đóng vai trò như VectorDB thu nhỏ)
document_chunks = []

# --- SCHEMAS ---
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

# --- HELPER FUNCTION: RAG RETRIEVAL CƠ BẢN ---
def retrieve_context(question: str, docs: List[str], top_k: int = 3) -> List[str]:
    """Hàm retrieve đơn giản dựa trên số từ trùng lặp (Word Overlap)"""
    if not docs: return []
    q_words = set(question.lower().split())
    scores = []
    for doc in docs:
        d_words = set(doc.lower().split())
        score = len(q_words.intersection(d_words))
        scores.append(score)
    # Lấy top_k chunks có điểm cao nhất
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    return [docs[i] for i in top_indices]

# --- API ENDPOINTS ---
@app.post("/upload", response_model=UploadResponse)
async def upload_document(req: UploadRequest):
    global document_chunks
    # 1. Chunking: Cắt tài liệu thành các đoạn (ví dụ 1000 ký tự/đoạn)
    chunk_size = 1000
    chunks = [req.text[i:i+chunk_size] for i in range(0, len(req.text), chunk_size)]
    
    # 2. Lưu vào DB (ở đây là biến global)
    document_chunks.extend(chunks)
    
    return UploadResponse(
        status="success",
        doc_id=req.doc_id or "default_doc",
        chunks=len(chunks)
    )

@app.post("/ask", response_model=AskResponse)
async def ask_question(req: AskRequest):
    # 1. Retrieve: Lấy ra các đoạn thông tin liên quan
    sources = retrieve_context(req.question, document_chunks, top_k=3)
    context_text = "\n---\n".join(sources)

    # 2. Cấu hình gọi Proxy LLM Server
    # LƯU Ý: Sử dụng MSSV B22DCVT415 làm API KEY
    client = OpenAI(
        base_url="http://192.168.50.218:8000/api/v1/proxy",
        api_key="B22DCVT415" 
    )

    # 3. Ép kiểu LLM trả về đúng 1 ký tự A, B, C hoặc D
    prompt = f"""Dựa vào thông tin sau:\n{context_text}\n
Hãy trả lời câu hỏi trắc nghiệm dưới đây. 
QUY ĐỊNH BẮT BUỘC: CHỈ ĐƯỢC PHÉP TRẢ VỀ ĐÚNG 1 KÝ TỰ LÀ ĐÁP ÁN ĐÚNG (A, B, C, hoặc D). Không giải thích gì thêm.
Câu hỏi: {req.question}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0 # Để câu trả lời có tính deterministic (ổn định)
        )
        answer = response.choices[0].message.content.strip().upper()
        
        # Đảm bảo format chỉ lấy 1 ký tự
        valid_choices = ['A', 'B', 'C', 'D']
        final_answer = answer[0] if len(answer) > 0 and answer[0] in valid_choices else 'A'

    except Exception as e:
        print(f"Lỗi gọi LLM: {e}")
        final_answer = 'A' # Trả về mặc định nếu lỗi để không bị crash

    return AskResponse(answer=final_answer, sources=sources)

if __name__ == "__main__":
    # Chạy server ở cổng 5050 để tránh đụng độ với AirPlay trên macOS
    uvicorn.run(app, host="0.0.0.0", port=5050)