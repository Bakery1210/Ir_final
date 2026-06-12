# 🏆 HƯỚNG DẪN THI RAG COMPETITION — 13/06/2026
## Bản OFFLINE — Đọc khi KHÔNG có Internet

> **MSSV:** B22DCVT415 | **Port:** 5050 | **Giới hạn:** 5 lần nộp | 100 câu/lần | Lấy điểm CAO NHẤT

---

## 📋 MỤC LỤC

1. [Tổng quan hệ thống](#-1-tổng-quan-hệ-thống)
2. [Trước khi vào phòng thi](#-2-trước-khi-vào-phòng-thi-checklist)
3. [Vào phòng thi — Từng bước](#-3-vào-phòng-thi--từng-bước)
4. [Chiến thuật 5 lần nộp](#-4-chiến-thuật-5-lần-nộp)
5. [Các lệnh Terminal cần nhớ](#-5-các-lệnh-terminal-cần-nhớ)
6. [Xử lý sự cố A-Z](#-6-xử-lý-sự-cố-a-z)
7. [Cheatsheet tóm tắt](#-7-cheatsheet-tóm-tắt)

---

## 🔰 1. TỔNG QUAN HỆ THỐNG

### Kiến trúc

```
┌─────────────────────────────┐         ┌──────────────────────────────┐
│   MÁY BẠN (Student)        │         │  MÁY GIÁO VIÊN (Teacher)    │
│                             │         │  IP: 192.168.50.218:8000     │
│  ┌───────────────────────┐  │         │                              │
│  │ student_server.py     │◄─┼────2────┤  Teacher Server              │
│  │ (FastAPI, port 5050)  │──┼────3───►│  - Gửi tài liệu (/upload)   │
│  │                       │◄─┼────4────┤  - Gửi 100 câu hỏi (/ask)   │
│  │ - Nhận tài liệu      │──┼────5───►│  - Chấm điểm                 │
│  │ - Chunking + Embed    │  │         │                              │
│  │ - Trả lời A/B/C/D    │  │         │  LLM Proxy (gpt-4o-mini)     │
│  └───────────────────────┘  │         │  - Giới hạn 4K tokens        │
│                             │         │  - Timeout 60s/câu           │
│  ┌───────────────────────┐  │         │                              │
│  │ run_competition.py    │──┼────1───►│  API endpoints:              │
│  │ (Client)              │◄─┼────6────┤  /api/v1/competition/...     │
│  │ - Đăng ký             │  │         │                              │
│  │ - Gọi evaluate        │  │         └──────────────────────────────┘
│  │ - Xem kết quả        │  │
│  └───────────────────────┘  │
└─────────────────────────────┘
```

### Luồng chấm điểm

```
1. Bạn gọi /register      → Đăng ký URL server bạn lên Teacher
2. Bạn gọi /evaluate       → Teacher bắt đầu chấm
3. Teacher gọi /upload      → Gửi tài liệu đến server bạn (lần đầu)
4. Server bạn chunking + embedding + lưu FAISS → trả response
5. Teacher gọi /ask 100 lần → Mỗi lần gửi 1 câu hỏi trắc nghiệm
6. Server bạn search + gọi LLM → trả A/B/C/D
7. Teacher chấm điểm → hiện kết quả
```

### 2 Phiên bản Server

| | `student_server.py` (v3.0) | `student_server_v2.py` (v3.1) |
|---|---|---|
| Model | `vietnamese-sbert` (768d) | `multilingual-e5-large` (1024d) |
| Tốc độ embed | ⚡ Nhanh hơn | 🐢 Chậm hơn |
| Chất lượng search | Tốt | Tốt hơn (có thể) |
| Kích thước model | ~400MB (đã tải) | ~1.2GB (cần tải) |
| Vector DB | `vector_db/` | `vector_db_v2/` |
| Dùng khi | Lần 1-3 (chắc ăn) | Lần 4-5 (thử nghiệm) |

> [!IMPORTANT]
> **Chiến lược:** Dùng `student_server.py` trước (model đã có sẵn, nhanh). Nếu còn lượt, thử `student_server_v2.py` xem điểm có cao hơn không.

---

## ✅ 2. TRƯỚC KHI VÀO PHÒNG THI (CHECKLIST)

### Đã hoàn thành trước đó

- [x] Code đã push lên GitHub
- [x] Repo là **public** (hoặc đã login GitHub trên máy thi)
- [x] Model `vietnamese-sbert` đã có trong `models/`
- [x] File `student_server.py` (v3.0) — sẵn sàng
- [x] File `student_server_v2.py` (v3.1) — backup với E5-Large
- [x] File `run_competition.py` — client đăng ký + chấm
- [x] Safety check 4K tokens đã thêm
- [x] Vector DB tự lưu disk + tự load lại

### Cần nhớ

- 📌 Link repo: `https://github.com/<username>/<repo-name>`
- 📌 MSSV: `B22DCVT415`
- 📌 Port: `5050`
- 📌 Teacher Server: `http://192.168.50.218:8000`
- 📌 Mạng thi: WiFi **ASUS_E0**

---

## 🚀 3. VÀO PHÒNG THI — TỪNG BƯỚC

### GIAI ĐOẠN 1: SETUP (0:00 → 0:07) — Cần Internet

#### Bước 1.1: Kết nối WiFi có Internet

Phòng thi có 2 mạng:

| Mạng | Dùng để | Khi nào |
|------|---------|---------|
| WiFi có Internet | Clone repo, cài pip, tải model | Setup ban đầu |
| **ASUS_E0** (LAN) | Kết nối Teacher Server | Khi thi |

> Kết nối WiFi có Internet **TRƯỚC** để clone + setup.

#### Bước 1.2: Clone repo

```bash
git clone https://github.com/<username>/<repo-name>.git
cd <repo-name>
```

#### Bước 1.3: Chạy setup tự động

```bash
bash setup.sh
```

> Nếu lỗi permission:
> ```bash
> chmod +x setup.sh && bash setup.sh
> ```

Script sẽ tự động:
1. Tạo `.venv/`
2. Cài dependencies từ `requirements.txt`
3. Tải model `vietnamese-sbert` → `models/vietnamese-sbert/`

⏱️ **Khoảng 3-5 phút**

#### Bước 1.4: Kiểm tra setup thành công

```bash
source .venv/bin/activate
python3 -c "from sentence_transformers import SentenceTransformer; m = SentenceTransformer('models/vietnamese-sbert'); print(f'OK! dim={m.get_embedding_dimension()}')"
```

Phải thấy: `OK! dim=768`

---

### GIAI ĐOẠN 2: KẾT NỐI MẠNG THI (0:07 → 0:08)

#### Bước 2.1: Chuyển sang WiFi ASUS_E0

- Disconnect WiFi Internet
- Connect WiFi **ASUS_E0**
- Hoặc nếu máy có LAN + WiFi: cắm LAN cho ASUS_E0, giữ WiFi Internet

#### Bước 2.2: Kiểm tra kết nối

```bash
ping 192.168.50.218
```

Phải thấy response. Nếu không → kiểm tra lại WiFi.

---

### GIAI ĐOẠN 3: CHẠY SERVER + THI (0:08 → 0:25)

> [!CAUTION]
> Từ đây trở đi cần **2 Terminal** mở song song. KHÔNG ĐƯỢC TẮT Terminal 1!

#### Bước 3.1: Terminal 1 — Chạy Student Server

```bash
cd <repo-name>
source .venv/bin/activate
python3 student_server.py
```

**Phải thấy dòng này:**
```
🚀 STUDENT RAG SERVER v3.0
📌 MSSV: B22DCVT415
🧠 Model: keepitreal/vietnamese-sbert
📦 DB: ⬜ Trống
⚡ Strategies: Parent-Child | BM25+Vector+RRF | MMR | Reorder | CoT
🌐 Port: 5050
INFO:     Uvicorn running on http://0.0.0.0:5050
```

> ⚠️ **KHÔNG ĐÓNG terminal này!** Để server chạy liên tục.

#### Bước 3.2: Terminal 2 — Chạy Client

```bash
cd <repo-name>
source .venv/bin/activate
python3 run_competition.py
```

**Menu hiện ra:**
```
🏆 RAG COMPETITION CLIENT — B22DCVT415
📡 Server URL: http://192.168.50.xxx:5050
📌 Giới hạn: 5 lần nộp | 100 câu/lần

  1. Đăng ký + Chấm điểm LẦN ĐẦU  (upload + hỏi)
  2. Chấm điểm LẦN SAU             (chỉ hỏi, ko upload)
  3. Xem kết quả hiện tại
  4. Reset trạng thái thi
  5. Chỉ đăng ký (register)
  6. Kiểm tra hệ thống (pre-flight)
  7. Thoát
```

#### Bước 3.3: Kiểm tra hệ thống (khuyến khích)

**Nhập `6`** → Kiểm tra pre-flight

Phải thấy tất cả ✅:
```
[1/3] Student Server (localhost:5050)... ✅ Running
[2/3] Teacher Server (http://192.168.50.218:8000/api/v1)... ✅ Connected
[3/3] LAN IP detection... ✅ 192.168.50.xxx
```

#### Bước 3.4: LẦN NỘP THỨ 1 — Đăng ký + Chấm điểm

**Nhập `1`** → Đăng ký + Evaluate lần đầu

Luồng diễn ra:
```
📝 ĐĂNG KÝ SERVER
   URL: http://192.168.50.xxx:5050
   ✅ Đăng ký thành công!

🎯 BẮT ĐẦU CHẤM ĐIỂM
   document_received: False
   → Sẽ upload tài liệu trước (~2 phút), sau đó gửi 100 câu hỏi

⚠️ Xác nhận bắt đầu evaluate? (y/n): y
```

**Sau khi nhấn `y`:**

1. Teacher Server gọi `POST /upload` → server bạn nhận tài liệu
2. Server chunking + embedding (~1-2 phút) → lưu FAISS
3. Teacher gửi 100 câu hỏi lần lượt
4. Mỗi câu: search → gọi LLM → trả A/B/C/D

**Trên Terminal 1 sẽ thấy:**
```
[UPLOAD] 📥 doc_id=..., length=... chars
[UPLOAD] ✅ 1/3 Chunking: XX parents, YY children
[UPLOAD] ⏳ 2/3 Embedding YY children...
[UPLOAD] 🎉 DONE! (XX.Xs)
[VectorStore] ✅ Saved to disk

[ASK] 📝 Câu hỏi 1...
[Search] Vector:20 → BM25:20 → RRF:... → MMR:5 → Parents:5
[Prompt] 📊 Estimated tokens: 1823/3800
[ASK] ✅ Đáp án: B (raw: 'B') [2.3s, attempt 1]

[ASK] 📝 Câu hỏi 2...
...
```

**Trên Terminal 2 (progress bar):**
```
[██████████████░░░░░░░░░░░░░░░░] 45/100 | Điểm: 32 | Status: evaluating
```

**Khi xong:**
```
🎉 ĐÃ CHẤM XONG!
📊 Kết quả: {'status': 'completed', 'score': XX, 'current_question': 100, ...}
```

> [!TIP]
> **Ghi lại điểm!** Ví dụ: Lần 1 = 65/100

---

### GIAI ĐOẠN 4: NỘP CÁC LẦN TIẾP THEO

#### Bước 4.1: Nộp lại KHÔNG cần upload (nhanh hơn ~2 phút)

**Nhập `2`** → Chấm lại (chỉ hỏi, không upload)

```
Luồng: reset() → evaluate(document_received=True) → get_result()
```

- ✅ KHÔNG upload lại tài liệu (tiết kiệm 2 phút)
- ✅ Vector DB đã lưu trên disk
- ✅ Teacher Server chỉ gửi 100 câu hỏi

> [!NOTE]
> Khi chọn 2, code tự gọi `/reset` trước, sau đó `/evaluate` với `document_received=True`.
> Điểm lần trước vẫn được giữ — hệ thống **lấy điểm cao nhất** trong 5 lần.

#### Bước 4.2: Muốn sửa code rồi nộp lại

```bash
# Terminal 1: Ctrl+C để tắt server
# Sửa code student_server.py (ví dụ: đổi prompt, thay TOP_K, ...)
# Chạy lại server:
source .venv/bin/activate
python3 student_server.py
# → Server tự load lại vector DB từ disk

# Terminal 2: Chọn 2 (chấm lại, không upload)
```

#### Bước 4.3: Muốn thử server v2 (E5-Large)

```bash
# Terminal 1: Ctrl+C tắt server cũ
python3 student_server_v2.py
# → Lần đầu sẽ tải model E5-Large (~1.2GB) — CẦN INTERNET
# → Hoặc nếu đã tải trước thì load từ models/multilingual-e5-large/

# Terminal 2:
python3 run_competition.py
# → Chọn 1 (cần upload lại vì vector DB v2 khác dimension)
```

> [!WARNING]
> Server v2 dùng **vector DB riêng** (`vector_db_v2/`), nên lần đầu chạy v2 phải chọn **1** (upload lại). Model E5-Large cần internet để tải nếu chưa có.

---

## 🧠 4. CHIẾN THUẬT 5 LẦN NỘP

> Lấy điểm **CAO NHẤT** trong 5 lần. Timeout upload: 120s. Timeout mỗi câu: 60s.

### Kế hoạch đề xuất

| Lần | Server | Thay đổi | Mục đích |
|:---:|--------|----------|----------|
| 1 | `student_server.py` | Chạy nguyên bản | Baseline — có điểm trước |
| 2 | `student_server.py` | Chọn 2 (không upload) | Kiểm tra tính ổn định |
| 3 | `student_server.py` | Tinh chỉnh config (nếu cần) | Tối ưu hóa |
| 4 | `student_server_v2.py` | Thử E5-Large (nếu còn internet) | Thử model mạnh hơn |
| 5 | Server nào điểm cao hơn | Giữ nguyên config tốt nhất | Lần cuối, chắc ăn |

### Các config có thể tinh chỉnh giữa các lần

Mở `student_server.py`, tìm phần `# CẤU HÌNH` ở đầu file:

```python
# Chunking — thử thay đổi kích thước chunk
PARENT_CHUNK_SIZE = 1000       # Thử: 800, 1200
PARENT_OVERLAP = 200           # Thử: 100, 300
CHILD_CHUNK_SIZE = 300         # Thử: 200, 400
CHILD_OVERLAP = 50             # Thử: 30, 80

# Retrieval — thử thay đổi số lượng kết quả
TOP_K_FINAL = 5                # Thử: 3, 4, 7
MMR_LAMBDA = 0.7               # Thử: 0.6, 0.8 (0.6 = đa dạng hơn)
```

> [!CAUTION]
> **CHỈ thay đổi 1 thứ mỗi lần!** Nếu thay nhiều thứ cùng lúc, không biết cái nào giúp/hại.

---

## 💻 5. CÁC LỆNH TERMINAL CẦN NHỚ

### Lệnh chính

```bash
# === SETUP ===
bash setup.sh                          # Setup tất cả
source .venv/bin/activate              # Kích hoạt venv

# === CHẠY SERVER ===
python3 student_server.py              # Server v3.0 (vietnamese-sbert)
python3 student_server_v2.py           # Server v3.1 (E5-Large)

# === CHẠY CLIENT ===
python3 run_competition.py             # Menu tương tác
python3 run_competition.py first       # CLI: Đăng ký + evaluate lần đầu
python3 run_competition.py again       # CLI: Reset + evaluate lại
python3 run_competition.py result      # CLI: Xem kết quả
python3 run_competition.py reset       # CLI: Reset trạng thái
python3 run_competition.py check       # CLI: Kiểm tra hệ thống
```

### Lệnh kiểm tra

```bash
# Kiểm tra kết nối
ping 192.168.50.218                    # Ping Teacher Server

# Kiểm tra Student Server
curl http://localhost:5050/             # Phải trả JSON status

# Kiểm tra IP LAN
ifconfig | grep 192.168                # Tìm IP trên mạng ASUS_E0

# Kiểm tra port
lsof -i :5050                          # Xem ai đang dùng port 5050
```

### Lệnh khẩn cấp

```bash
# Port bị chiếm
lsof -i :5050                          # Tìm PID
kill -9 <PID>                          # Kill process

# Xóa vector DB để upload lại
rm -rf vector_db/                      # Xóa DB v1
rm -rf vector_db_v2/                   # Xóa DB v2

# Xóa venv, tạo lại
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Tải lại model
python3 -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('keepitreal/vietnamese-sbert')
model.save('models/vietnamese-sbert')
print('Done!')
"
```

---

## 🔧 6. XỬ LÝ SỰ CỐ A-Z

### ❌ "Student Server chưa chạy"

**Nguyên nhân:** Chưa chạy `python3 student_server.py` ở Terminal 1

**Fix:**
```bash
# Terminal 1:
cd <repo-name>
source .venv/bin/activate
python3 student_server.py
```

---

### ❌ "Không kết nối được Teacher Server"

**Nguyên nhân:** Chưa kết nối WiFi ASUS_E0

**Fix:**
1. Kiểm tra WiFi → kết nối **ASUS_E0**
2. `ping 192.168.50.218` → phải có response
3. Nếu máy có LAN: cắm dây LAN vào switch phòng thi

---

### ❌ "Port 5050 đang bị chiếm"

**Nguyên nhân:** Server cũ chưa tắt hẳn

**Fix:**
```bash
lsof -i :5050
# Tìm PID, ví dụ: python3  12345
kill -9 12345
# Chạy lại server
python3 student_server.py
```

---

### ❌ "Model not found" hoặc lỗi load model

**Nguyên nhân:** Chưa tải model về local

**Fix (cần internet):**
```bash
source .venv/bin/activate
python3 -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('keepitreal/vietnamese-sbert')
model.save('models/vietnamese-sbert')
print('Done!')
"
```

---

### ❌ Upload bị timeout (> 120s)

**Nguyên nhân:** Embedding quá nhiều chunks, model chậm

**Fix:** Giảm số chunks bằng cách tăng chunk size:
```python
# Trong student_server.py, dòng ~41-44:
PARENT_CHUNK_SIZE = 1500       # Tăng từ 1000 → ít parent chunks hơn
CHILD_CHUNK_SIZE = 500         # Tăng từ 300 → ít child chunks hơn
```
Sau đó tắt server → chạy lại → chọn **1** (upload lại).

---

### ❌ LLM trả về sai format (không phải A/B/C/D)

**Hệ thống đã xử lý:** Code tự parse tìm ký tự A/B/C/D đầu tiên. Nếu không tìm thấy → trả mặc định `A`.

---

### ❌ Evaluate bị timeout (> 10 phút)

**Fix:**
1. Chọn **3** (Xem kết quả) để kiểm tra tiến độ
2. Nếu `status='completed'` → đã xong, xem điểm
3. Nếu `status='evaluating'` → đang chấm, đợi thêm
4. Nếu `status='error'` → chọn **4** (Reset) rồi thử lại

---

### ❌ Server crash giữa chừng

**Fix:**
```bash
# Terminal 1: Sửa code nếu cần, rồi chạy lại
python3 student_server.py
# → Server tự load lại vector DB từ disk

# Terminal 2:
python3 run_competition.py
# → Chọn 2 (chấm lại, không upload)
```

---

### ❌ Lỗi pip / thiếu thư viện

**Fix:**
```bash
source .venv/bin/activate
pip install fastapi uvicorn openai sentence-transformers faiss-cpu numpy requests
```

---

### ❌ "Đã hết 5 lượt nộp"

**Không thể fix.** Giới hạn do Teacher Server kiểm soát. Reset KHÔNG xóa bộ đếm lượt nộp.

Hệ thống lấy **điểm cao nhất** → điểm cuối cùng của bạn là MAX trong 5 lần.

---

### ❌ Vector DB trống khi chọn 2

**Nguyên nhân:** Chưa upload lần nào hoặc `vector_db/` bị xóa

**Fix:** Chọn **1** thay vì **2** (để upload tài liệu lại)

---

### ❌ IP detect sai (127.0.0.1)

**Nguyên nhân:** Chưa kết nối WiFi ASUS_E0

**Fix:**
1. Kết nối WiFi ASUS_E0
2. Tắt client (Ctrl+C) → chạy lại `python3 run_competition.py`
3. IP sẽ tự detect lại

---

## 📌 7. CHEATSHEET TÓM TẮT

### ⏱️ Timeline trong phòng thi

```
0:00 ─── Kết nối WiFi Internet
0:01 ─── git clone + cd repo
0:02 ─── bash setup.sh (chờ 3-5 phút)
0:07 ─── Chuyển WiFi → ASUS_E0
0:08 ─── [Terminal 1] python3 student_server.py
0:09 ─── [Terminal 2] python3 run_competition.py
0:09 ─── Chọn 6 (kiểm tra hệ thống)
0:10 ─── Chọn 1 (đăng ký + evaluate lần 1)
0:10 ─── Chờ upload tài liệu (~2 phút)
0:12 ─── Chờ chấm 100 câu (~10-15 phút)
0:25 ─── ✅ XEM ĐIỂM LẦN 1
0:26 ─── Chọn 2 (evaluate lần 2, không upload)
0:35 ─── ✅ XEM ĐIỂM LẦN 2
0:36 ─── (Tùy) Sửa code → tắt server → chạy lại → Chọn 2
0:45 ─── ✅ XEM ĐIỂM LẦN 3
  ...tiếp tục đến lần 5 nếu cần...
```

### Quy tắc vàng

```
┌──────────────────────────────────────────────┐
│  📌 5 lần nộp — LẤY ĐIỂM CAO NHẤT          │
│  📌 100 câu hỏi — timeout 60s/câu           │
│  📌 Upload timeout: 120 giây                 │
│  📌 LLM token limit: 4K                     │
│  📌 Answer: CHỈ 1 ký tự A/B/C/D             │
│  📌 KHÔNG TẮT Terminal 1 (server)            │
│  📌 Chọn 2 để thi lại NHANH (skip upload)   │
│  📌 Vector DB tự lưu disk, tự load lại      │
│  📌 Sửa code → tắt server → chạy lại → OK   │
└──────────────────────────────────────────────┘
```

### Menu nhanh

```
Chọn 1 → LẦN ĐẦU (register + upload + 100 câu)     ← Dùng lần 1
Chọn 2 → LẦN SAU (reset + chỉ hỏi, không upload)   ← Dùng lần 2-5
Chọn 3 → Xem điểm hiện tại
Chọn 4 → Reset trạng thái (nếu bị lỗi)
Chọn 5 → Chỉ đăng ký lại (nếu cần)
Chọn 6 → Kiểm tra hệ thống
Chọn 7 → Thoát
```

### Cấu trúc thư mục sau khi chạy

```
<repo-name>/
├── student_server.py        ← SERVER CHÍNH (chạy file này)
├── student_server_v2.py     ← SERVER BACKUP (E5-Large)
├── run_competition.py       ← CLIENT (đăng ký + chấm)
├── requirements.txt
├── setup.sh
├── HUONG_DAN_THI.md
├── .gitignore
│
├── .venv/                   ← Python virtual environment
├── models/
│   ├── vietnamese-sbert/    ← Model v1 (đã có)
│   └── multilingual-e5-large/  ← Model v2 (tải khi dùng v2)
├── vector_db/               ← FAISS DB cho v1 (tạo khi upload)
│   ├── index.faiss
│   └── data.pkl
└── vector_db_v2/            ← FAISS DB cho v2 (tạo khi upload)
    ├── index.faiss
    └── data.pkl
```

---

> [!TIP]
> **Bình tĩnh là chìa khóa.** Server đã được code kỹ với error handling, auto-retry, và vector DB persistence. Nếu gặp lỗi → đọc log trên Terminal 1, nó sẽ gợi ý cách fix.

**Chúc thi tốt! 🎯**
