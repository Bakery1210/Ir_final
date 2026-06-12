# 📋 HƯỚNG DẪN THI RAG COMPETITION - Ngày 13/06/2026

> **MSSV:** B22DCVT415  
> **Server port:** 5050  
> **Giới hạn:** 5 lần nộp | 100 câu hỏi/lần

---

## ⚡ QUICK START (Chỉ cần 3 bước)

```bash
# Bước 1: Clone repo + setup
git clone https://github.com/<username>/<repo-name>.git
cd <repo-name>
bash setup.sh

# Bước 2: Chạy server (Terminal 1)
source .venv/bin/activate
python3 student_server.py

# Bước 3: Chạy client (Terminal 2)  
source .venv/bin/activate
python3 run_competition.py
# → Chọn 1 để bắt đầu
```

---

## 📖 HƯỚNG DẪN CHI TIẾT TỪNG BƯỚC

### Bước 0: Trước khi vào phòng thi
- [ ] Đảm bảo code đã push lên GitHub
- [ ] Nhớ link repo: `https://github.com/<username>/<repo-name>`
- [ ] Đảm bảo repo là **public** (hoặc đã login GitHub trên máy thi)

### Bước 1: Kết nối mạng

Phòng thi có **2 mạng**:
| Mạng | Mục đích |
|------|----------|
| **ASUS_E0** (LAN) | Kết nối Teacher Server (192.168.50.218) — **BẮT BUỘC** |
| WiFi có Internet | Để clone repo, cài pip, tải model — **Dùng lúc setup** |

> ⚠️ **Quan trọng:** Kết nối WiFi có Internet trước để clone + setup, sau đó chuyển sang ASUS_E0 để thi.
> Hoặc nếu máy có 2 card mạng (WiFi + Ethernet), dùng cả 2 cùng lúc.

### Bước 2: Clone repo

```bash
# Mở Terminal
git clone https://github.com/<username>/<repo-name>.git
cd <repo-name>
```

### Bước 3: Chạy setup tự động

```bash
bash setup.sh
```

Script sẽ tự động:
1. Tạo Python virtual environment (`.venv/`)
2. Cài tất cả dependencies từ `requirements.txt`
3. Tải model `keepitreal/vietnamese-sbert` về local (`models/`)

⏱️ **Thời gian ước tính:** 3-5 phút (tùy tốc độ mạng)

> Nếu `bash setup.sh` bị lỗi permission:
> ```bash
> chmod +x setup.sh && bash setup.sh
> ```

### Bước 4: Đổi sang mạng ASUS_E0

> Nếu chưa kết nối ASUS_E0, hãy kết nối bây giờ.  
> Teacher Server: `http://192.168.50.218:8000`

### Bước 5: Chạy Student Server (Terminal 1)

```bash
source .venv/bin/activate
python3 student_server.py
```

Khi thấy dòng này là server đã sẵn sàng:
```
🚀 Starting Student Server on port 5050...
INFO:     Uvicorn running on http://0.0.0.0:5050
```

> ⚠️ **KHÔNG ĐƯỢC TẮT terminal này!** Server phải chạy liên tục.

### Bước 6: Chạy Competition Client (Terminal 2 — mở terminal mới)

```bash
cd <repo-name>
source .venv/bin/activate
python3 run_competition.py
```

Menu hiện ra:
```
  🏆 RAG COMPETITION CLIENT - B22DCVT415
  1. Đăng ký + Chấm điểm LẦN ĐẦU (upload tài liệu + hỏi)
  2. Chấm điểm LẦN SAU (chỉ hỏi, không upload lại)
  3. Xem kết quả hiện tại
  4. Reset trạng thái thi
  5. Chỉ đăng ký (register)
  6. Thoát
```

#### Lần thi đầu tiên: Chọn `1`
- Teacher Server sẽ gửi tài liệu → server bạn chunking + embedding + lưu FAISS (~2 phút)
- Sau đó gửi 100 câu hỏi lần lượt
- Xem điểm cuối cùng

#### Muốn thi lại: Chọn `2`
- Tự động reset + gọi evaluate với `document_received=True`
- **KHÔNG upload lại** → tiết kiệm 2 phút
- Vector DB đã lưu sẵn trên disk

---

## 🔄 CÁC TÌNH HUỐNG XỬ LÝ SỰ CỐ

### ❌ Server bị crash / cần sửa code
```bash
# Terminal 1: Ctrl+C để tắt server
# Sửa code student_server.py
# Chạy lại:
source .venv/bin/activate
python3 student_server.py
# → Server tự load lại vector DB từ disk, KHÔNG cần upload lại
# Terminal 2: Chọn 2 (chấm lại, không upload)
```

### ❌ Không kết nối được Teacher Server
1. Kiểm tra đã kết nối WiFi **ASUS_E0** chưa
2. Thử ping: `ping 192.168.50.218`
3. Kiểm tra IP LAN: `ifconfig | grep 192.168`

### ❌ Lỗi "model not found"
```bash
# Tải lại model
source .venv/bin/activate
python3 -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('keepitreal/vietnamese-sbert')
model.save('models/vietnamese-sbert')
print('Done!')
"
```

### ❌ Port 5050 đang bị chiếm
```bash
# Tìm và kill process đang dùng port 5050
lsof -i :5050
kill -9 <PID>
```

### ❌ Lỗi pip / venv
```bash
# Xóa venv cũ, tạo lại
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 📁 CẤU TRÚC THƯ MỤC

```
<repo-name>/
├── student_server.py      # Server RAG chính (FastAPI)
├── run_competition.py     # Client đăng ký + chấm điểm
├── requirements.txt       # Dependencies
├── setup.sh               # Script setup tự động
├── .gitignore             # Loại trừ venv, models, vector_db
├── HUONG_DAN_THI.md       # File này
├── models/                # (Tạo bởi setup.sh)
│   └── vietnamese-sbert/  #   Model embedding local
└── vector_db/             # (Tạo khi upload lần đầu)
    ├── index.faiss        #   FAISS index
    └── chunks.pkl         #   Text chunks
```

---

## ⏱️ TIMELINE DỰ KIẾN TRONG PHÒNG THI

| Thời gian | Việc cần làm |
|-----------|-------------|
| 0:00 - 0:02 | Kết nối WiFi Internet, clone repo |
| 0:02 - 0:07 | Chạy `bash setup.sh` (cài deps + tải model) |
| 0:07 - 0:08 | Chuyển sang WiFi ASUS_E0 |
| 0:08 - 0:09 | Chạy `python3 student_server.py` |
| 0:09 - 0:10 | Chạy `python3 run_competition.py` → Chọn 1 |
| 0:10 - 0:12 | Chờ upload tài liệu (~2 phút) |
| 0:12 - 0:25 | Chờ chấm 100 câu |
| 0:25+      | Xem điểm, nếu cần → sửa code → Chọn 2 (thi lại) |

> ⚠️ **NHỚ: Tối đa 5 lần nộp!** Hãy cân nhắc kỹ trước khi chạy evaluate.

---

## 📌 LƯU Ý QUAN TRỌNG

1. **Tối đa 5 lần nộp** — quá 5 lần điểm cao cũng không tính
2. **100 câu hỏi** mỗi lần chấm
3. **Timeout upload: 120 giây** — nếu embedding chậm quá sẽ bị timeout
4. **Timeout mỗi câu hỏi: 60 giây**
5. Endpoint phải đúng path có `/v1`: `http://192.168.50.218:8000/api/v1/...`
6. Header bắt buộc: `X-Student-ID: B22DCVT415`
7. Answer chỉ được là 1 ký tự: `A`, `B`, `C`, hoặc `D`
