@echo off
chcp 65001 >nul
:: ============================================================
:: SETUP SCRIPT - Chay 1 lan sau khi clone repo (Danh cho Windows)
:: MSSV: B22DCVT415
:: ============================================================

echo ============================================================
echo   🚀 SETUP HE THONG RAG COMPETITION (WINDOWS)
echo   MSSV: B22DCVT415
echo ============================================================
echo.

:: Xac dinh lenh Python
python --version >nul 2>&1
if %ERRORLEVEL% == 0 (
    set PY_CMD=python
) else (
    py --version >nul 2>&1
    if %ERRORLEVEL% == 0 (
        set PY_CMD=py
    ) else (
        echo [X] Khong tim thay Python! Vui long cai dat Python.
        pause
        exit /b 1
    )
)

:: 1. Tao Virtual Environment
echo [1/4] Tao Virtual Environment...
if not exist ".venv\" (
    %PY_CMD% -m venv .venv
    echo   [OK] Da tao .venv
) else (
    echo   [-] .venv da ton tai, bo qua
)

:: 2. Kich hoat venv
echo [2/4] Kich hoat .venv...
call .venv\Scripts\activate.bat
echo   [OK] Python trong venv da san sang

:: 3. Cai dependencies
echo [3/4] Cai dat dependencies...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt
echo   [OK] Da cai xong dependencies

:: 4. Tai model embedding
echo [4/4] Tai model keepitreal/vietnamese-sbert...
if exist "models\vietnamese-sbert\" (
    echo   [-] Model sbert da co san, bo qua
) else (
    python -c "from sentence_transformers import SentenceTransformer; import os; print('  Dang tai tu HuggingFace...'); model = SentenceTransformer('keepitreal/vietnamese-sbert'); os.makedirs('models/vietnamese-sbert', exist_ok=True); model.save('models/vietnamese-sbert'); print('  [OK] Da luu model vao models/vietnamese-sbert')"
)

:: 5. Tai model E5-Large (Backup)
echo [5/5] Tai model backup intfloat/multilingual-e5-large (~1.2GB)...
if exist "models\multilingual-e5-large\" (
    echo   [-] Model E5-Large da co san, bo qua
) else (
    python -c "from sentence_transformers import SentenceTransformer; import os; print('  Dang tai E5-Large tu HuggingFace (Co the mat 5-10 phut)...'); model = SentenceTransformer('intfloat/multilingual-e5-large'); os.makedirs('models/multilingual-e5-large', exist_ok=True); model.save('models/multilingual-e5-large'); print('  [OK] Da luu model vao models/multilingual-e5-large')"
)

echo.
echo ============================================================
echo   [OK] SETUP HOAN TAT!
echo ============================================================
echo.
echo   Buoc tiep theo:
echo   Terminal 1:  .venv\Scripts\activate ^&^& python student_server.py
echo   Terminal 2:  .venv\Scripts\activate ^&^& python run_competition.py
echo.
pause
