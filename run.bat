@echo off
title 知識管理系統
echo 正在啟動知識管理系統...
echo.

REM 檢查是否有 uv 環境
uv --version >nul 2>&1
if not errorlevel 1 (
    echo 檢測到 uv 環境，使用 uv 管理依賴...
    
    REM 確保依賴已安裝
    echo 檢查依賴套件...
    uv sync
    if errorlevel 1 (
        echo 錯誤: uv 依賴安裝失敗
        pause
        exit /b 1
    )
    
    REM 使用 uv 運行應用程式
    echo 啟動知識管理系統...
    uv run python main.py
    goto :end
)

REM 回退到標準 Python 環境
echo 未檢測到 uv，使用標準 Python 環境...

REM 檢查是否有 Python 環境
python --version >nul 2>&1
if errorlevel 1 (
    echo 錯誤: 未找到 Python 環境，請先安裝 Python 3.11 或更高版本
    echo 建議安裝 uv 來管理此項目: https://docs.astral.sh/uv/
    pause
    exit /b 1
)

REM 檢查是否安裝了必要套件
python -c "import webview" >nul 2>&1
if errorlevel 1 (
    echo 正在安裝必要套件...
    pip install pywebview flask flask-sqlalchemy flask-migrate python-dotenv pillow
    if errorlevel 1 (
        echo 錯誤: 套件安裝失敗
        pause
        exit /b 1
    )
)

REM 啟動應用程式
echo 啟動知識管理系統...
python main.py

:end
if errorlevel 1 (
    echo.
    echo 應用程式執行時發生錯誤
    pause
)