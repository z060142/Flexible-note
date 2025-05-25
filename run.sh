#!/bin/bash

echo "正在啟動知識管理系統..."
echo

# 檢查是否有 uv 環境
if command -v uv &> /dev/null; then
    echo "檢測到 uv 環境，使用 uv 管理依賴..."
    
    # 確保依賴已安裝
    echo "檢查依賴套件..."
    uv sync
    if [ $? -ne 0 ]; then
        echo "錯誤: uv 依賴安裝失敗"
        exit 1
    fi
    
    # 使用 uv 運行應用程式
    echo "啟動知識管理系統..."
    uv run python main.py
    
    if [ $? -ne 0 ]; then
        echo
        echo "應用程式執行時發生錯誤"
        read -p "按 Enter 鍵退出..."
    fi
    
    exit 0
fi

# 回退到標準 Python 環境
echo "未檢測到 uv，使用標準 Python 環境..."

# 檢查是否有 Python 環境
if ! command -v python3 &> /dev/null; then
    echo "錯誤: 未找到 Python 環境，請先安裝 Python 3.11 或更高版本"
    echo "建議安裝 uv 來管理此項目: https://docs.astral.sh/uv/"
    exit 1
fi

# 檢查 Python 版本
python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
required_version="3.11"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "錯誤: 需要 Python $required_version 或更高版本，當前版本為 $python_version"
    exit 1
fi

# 檢查是否安裝了必要套件
if ! python3 -c "import webview" &> /dev/null; then
    echo "正在安裝必要套件..."
    
    # 嘗試使用 pip 或 pip3
    if command -v pip3 &> /dev/null; then
        pip3 install pywebview flask flask-sqlalchemy flask-migrate python-dotenv pillow
    elif command -v pip &> /dev/null; then
        pip install pywebview flask flask-sqlalchemy flask-migrate python-dotenv pillow
    else
        echo "錯誤: 未找到 pip，請先安裝 pip"
        exit 1
    fi
    
    if [ $? -ne 0 ]; then
        echo "錯誤: 套件安裝失敗"
        exit 1
    fi
fi

# 檢查作業系統並安裝相應的 WebView 依賴
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS - 通常不需要額外的依賴
    echo "檢測到 macOS 系統"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux - 可能需要安裝 GTK 依賴
    echo "檢測到 Linux 系統"
    echo "注意: 如果遇到 GTK 相關錯誤，請安裝相應的系統依賴："
    echo "Ubuntu/Debian: sudo apt-get install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.0"
    echo "CentOS/RHEL: sudo yum install python3-gobject gtk3-devel webkit2gtk3-devel"
fi

# 設置執行權限（如果需要）
chmod +x "$0"

# 啟動應用程式
echo "啟動知識管理系統..."
python3 main.py

if [ $? -ne 0 ]; then
    echo
    echo "應用程式執行時發生錯誤"
    read -p "按 Enter 鍵退出..."
fi