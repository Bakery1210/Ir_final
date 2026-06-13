#!/bin/bash
# ============================================================
# SETUP SCRIPT - Chạy 1 lần sau khi clone repo
# MSSV: B22DCVT415
# ============================================================

set -e

echo "============================================================"
echo "  🚀 SETUP HỆ THỐNG RAG COMPETITION"
echo "  MSSV: B22DCVT415"
echo "============================================================"
echo ""

# Xác định lệnh Python
if command -v python3 &>/dev/null; then
    PY_CMD="python3"
elif command -v python &>/dev/null; then
    PY_CMD="python"
else
    echo "❌ Không tìm thấy Python! Vui lòng cài đặt Python (phiên bản 3.8 trở lên)."
    exit 1
fi

# 1. Tạo Virtual Environment
echo "[1/4] Tạo Virtual Environment..."
if [ ! -d ".venv" ]; then
    $PY_CMD -m venv .venv
    echo "  ✅ Đã tạo .venv"
else
    echo "  ⏩ .venv đã tồn tại, bỏ qua"
fi

# 2. Kích hoạt venv
echo "[2/4] Kích hoạt .venv..."
source .venv/bin/activate
echo "  ✅ Python: $(which python)"

# 3. Cài dependencies
echo "[3/4] Cài đặt dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "  ✅ Đã cài xong dependencies"

# 4. Tải model embedding
echo "[4/4] Tải model keepitreal/vietnamese-sbert..."
if [ -d "models/vietnamese-sbert" ]; then
    echo "  ⏩ Model sbert đã có sẵn, bỏ qua"
else
    python -c "
from sentence_transformers import SentenceTransformer
import os
print('  Đang tải từ HuggingFace...')
model = SentenceTransformer('keepitreal/vietnamese-sbert')
os.makedirs('models/vietnamese-sbert', exist_ok=True)
model.save('models/vietnamese-sbert')
print('  ✅ Đã lưu model vào models/vietnamese-sbert')
# Quick test
test = model.encode(['Test'])
print(f'  ✅ Model test OK - embedding dim: {test.shape[1]}')
"
fi

# 5. Tải model E5-Large (Backup)
echo "[5/5] Tải model backup intfloat/multilingual-e5-large (~1.2GB)..."
if [ -d "models/multilingual-e5-large" ]; then
    echo "  ⏩ Model E5-Large đã có sẵn, bỏ qua"
else
    python -c "
from sentence_transformers import SentenceTransformer
import os
print('  Đang tải E5-Large từ HuggingFace (Có thể mất 5-10 phút)...')
model = SentenceTransformer('intfloat/multilingual-e5-large')
os.makedirs('models/multilingual-e5-large', exist_ok=True)
model.save('models/multilingual-e5-large')
print('  ✅ Đã lưu model vào models/multilingual-e5-large')
"
fi

echo ""
echo "============================================================"
echo "  ✅ SETUP HOÀN TẤT!"
echo "============================================================"
echo ""
echo "  Bước tiếp theo:"
echo "  Terminal 1:  source .venv/bin/activate && python student_server.py"
echo "  Terminal 2:  source .venv/bin/activate && python run_competition.py"
echo ""
