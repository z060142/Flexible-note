#!/usr/bin/env python3
"""
知識管理系統 - WebView 桌面應用啟動器
"""

import os
import sys
import threading
import time
import socket
import webbrowser
from contextlib import closing
import webview
# Updated import: create_app is the factory, db is the SQLAlchemy instance
from app import create_app, db 


def find_free_port():
    """尋找一個可用的端口"""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('localhost', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


def is_port_available(port):
    """檢查端口是否可用"""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        try:
            s.bind(('localhost', port))
            return True
        except OSError:
            return False


def ensure_upload_folder():
    """確保上傳資料夾存在"""
    # app will be available globally in this script after main() instantiates it.
    # However, it's better practice to pass app if this function could be called before main().
    # For this specific script structure, direct access after main() sets it is okay.
    upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder, exist_ok=True)
        print(f"創建上傳資料夾: {upload_folder}")


def start_flask_server(port):
    """在獨立線程中啟動Flask伺服器"""
    def run_server():
        try:
            # 確保資料庫和上傳資料夾
            with app.app_context():
                db.create_all()
                ensure_upload_folder()
            
            # 啟動Flask應用，關閉debug模式以避免重新載入
            print(f"Flask伺服器啟動於 http://localhost:{port}")
            app.run(
                host='localhost',
                port=port,
                debug=False,  # 關閉debug模式
                use_reloader=False,  # 關閉自動重載
                threaded=True
            )
        except Exception as e:
            print(f"Flask伺服器啟動失敗: {e}")
            sys.exit(1)
    
    # 在daemon線程中運行，這樣主程序退出時它也會退出
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    return server_thread


def wait_for_server(port, timeout=30):
    """等待Flask伺服器啟動"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
                s.settimeout(1)
                result = s.connect_ex(('localhost', port))
                if result == 0:
                    print("Flask伺服器已就緒")
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    
    print("等待Flask伺服器啟動超時")
    return False


class KnowledgeSystemAPI:
    """WebView API 類，用於與前端JavaScript交互"""
    
    def __init__(self):
        self.app_name = "知識管理系統"
        self.version = "1.0.0"
    
    def get_app_info(self):
        """獲取應用資訊"""
        return {
            "name": self.app_name,
            "version": self.version,
            "platform": sys.platform
        }
    
    def open_external_link(self, url):
        """在外部瀏覽器中打開連結"""
        try:
            webbrowser.open(url)
            return True
        except Exception as e:
            print(f"無法打開外部連結: {e}")
            return False
    
    def show_notification(self, title, message):
        """顯示系統通知（如果支援）"""
        print(f"通知 - {title}: {message}")
        return True


def create_webview_window(port):
    """創建WebView視窗"""
    api = KnowledgeSystemAPI()
    
    # WebView視窗配置
    window_config = {
        'title': '知識管理系統',
        'url': f'http://localhost:{port}',
        'width': 1200,
        'height': 800,
        'min_size': (800, 600),
        'resizable': True,
        'fullscreen': False,
        'minimized': False,
        'on_top': False,
        'shadow': True,
        'focus': True,
        'js_api': api
    }
    
    # 根據作業系統調整設定
    if sys.platform == 'win32':
        window_config['text_select'] = False  # Windows特定設定
    elif sys.platform == 'darwin':
        window_config['title_bar_color'] = '#2c3e50'  # macOS特定設定
    
    return webview.create_window(**window_config)


def main():
    """主函數"""
    global app # Declare app as global so functions outside main can see the instance created here
    app = create_app() # Instantiate the app using the factory

    print("正在啟動知識管理系統...")
    
    # 尋找可用端口
    default_port = 5000
    port = default_port if is_port_available(default_port) else find_free_port()
    
    print(f"使用端口: {port}")
    
    # 啟動Flask伺服器
    flask_thread = start_flask_server(port)
    
    # 等待伺服器啟動
    if not wait_for_server(port):
        print("Flask伺服器啟動失敗，程序退出")
        sys.exit(1)
    
    try:
        # 創建WebView視窗
        window = create_webview_window(port)
        
        print("正在啟動WebView視窗...")
        
        # 啟動WebView（這會阻塞直到視窗關閉）
        webview.start(
            debug=False,  # 生產環境設為False，開發時可設為True
            http_server=False,  # 我們使用自己的Flask伺服器
            user_agent='KnowledgeSystem/1.0'
        )
        
    except KeyboardInterrupt:
        print("\n收到中斷信號，正在關閉應用...")
    except Exception as e:
        print(f"WebView啟動失敗: {e}")
        sys.exit(1)
    finally:
        print("應用已關閉")


if __name__ == '__main__':
    main()