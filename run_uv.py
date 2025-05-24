#!/usr/bin/env python3
"""
使用 uv 環境的快速啟動腳本
這個腳本會檢查 uv 環境並直接啟動應用程式
"""

import os
import sys
import subprocess


def check_uv():
    """檢查 uv 是否可用"""
    try:
        result = subprocess.run(['uv', '--version'], 
                              capture_output=True, text=True, check=True)
        print(f"檢測到 uv: {result.stdout.strip()}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def sync_dependencies():
    """同步 uv 依賴"""
    try:
        print("正在同步依賴...")
        subprocess.run(['uv', 'sync'], check=True)
        print("依賴同步完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"依賴同步失敗: {e}")
        return False


def run_app():
    """使用 uv 運行應用程式"""
    try:
        print("正在啟動知識管理系統...")
        subprocess.run(['uv', 'run', 'python', 'main.py'], check=True)
    except subprocess.CalledProcessError as e:
        print(f"應用程式啟動失敗: {e}")
        return False
    except KeyboardInterrupt:
        print("\n收到中斷信號，正在關閉應用...")
    return True


def main():
    """主函數"""
    print("=== 知識管理系統 - uv 啟動器 ===")
    print()
    
    # 檢查是否在正確的目錄
    if not os.path.exists('pyproject.toml'):
        print("錯誤: 未找到 pyproject.toml 文件")
        print("請確保您在項目根目錄下運行此腳本")
        sys.exit(1)
    
    # 檢查 uv
    if not check_uv():
        print("錯誤: 未找到 uv 包管理器")
        print("請先安裝 uv: https://docs.astral.sh/uv/")
        print()
        print("安裝命令:")
        print("  macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh")
        print("  Windows:     powershell -c \"irm https://astral.sh/uv/install.ps1 | iex\"")
        sys.exit(1)
    
    # 同步依賴
    if not sync_dependencies():
        print("無法繼續，依賴同步失敗")
        sys.exit(1)
    
    # 運行應用程式
    print()
    if not run_app():
        sys.exit(1)
    
    print("應用程式已關閉")


if __name__ == '__main__':
    main()