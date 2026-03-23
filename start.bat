@echo off
chcp 65001 > nul
title In file PDF

echo ============================================================
echo   Kiem tra / cai dat thu vien...
echo ============================================================
pip install -r requirements.txt --quiet

echo.
echo ============================================================
echo   Khoi dong In file PDF...
echo ============================================================
python app.py

pause
