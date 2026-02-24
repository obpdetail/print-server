@echo off
chcp 65001 > nul
title Print Server

echo ============================================================
echo   Kiem tra / cai dat thu vien...
echo ============================================================
pip install -r requirements.txt --quiet

echo.
echo ============================================================
echo   Khoi dong Print Server...
echo ============================================================
python app.py

pause
