# 知識管理系統 - WebView 桌面版

這是一個基於 Flask 和 PyWebView 的桌面知識管理系統，無需瀏覽器即可運行。

## 系統需求

- Python 3.11 或更高版本
- [uv](https://docs.astral.sh/uv/) 包管理器（推薦，但非必需）
- 作業系統支援：
  - Windows 10/11
  - macOS 10.14+
  - Linux (Ubuntu 18.04+, CentOS 7+)

## 項目設置

### 如果您有 uv（推薦）

```bash
# 克隆項目後，同步依賴
uv sync

# 初始化資料庫
uv run flask db upgrade

# 啟動應用程式
uv run python main.py
```

### 如果您使用標準 Python

```bash
# 創建虛擬環境（可選但推薦）
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate     # Windows

# 安裝依賴
pip install pywebview flask flask-sqlalchemy flask-migrate python-dotenv pillow

# 啟動應用程式
python main.py
```

## 安裝與啟動

### 方法一：使用啟動腳本（推薦）

#### Windows 用戶
1. 雙擊運行 `run.bat`
2. 腳本會自動檢測並使用 `uv` 環境（如果有）
3. 如果沒有 `uv`，會回退到標準 Python 環境
4. 等待桌面應用視窗開啟

#### macOS/Linux 用戶
1. 在終端中執行：
   ```bash
   chmod +x run.sh
   ./run.sh
   ```
2. 腳本會自動檢測並使用 `uv` 環境（如果有）
3. 如果沒有 `uv`，會回退到標準 Python 環境
4. 等待桌面應用視窗開啟

### 方法二：使用 uv（推薦開發者）

如果你已經安裝了 [uv](https://docs.astral.sh/uv/)：

```bash
# 同步依賴
uv sync

# 啟動應用程式
uv run python main.py
```

### 方法二：使用 UV 專用啟動器

如果你已經安裝了 [uv](https://docs.astral.sh/uv/)，可以使用專用的啟動器：

```bash
# 使用 UV 專用啟動器
python run_uv.py
```

這個啟動器會：
- 自動檢測 uv 環境
- 同步所有依賴 (`uv sync`)
- 啟動桌面應用程式

### 方法三：手動使用 uv

如果你已經安裝了 [uv](https://docs.astral.sh/uv/)：

```bash
# 同步依賴
uv sync

# 啟動應用程式
uv run python main.py
```

> **💡 小提示**: uv 是更快、更現代的 Python 包管理器。如果您還沒有安裝，建議先安裝 uv：
> ```bash
> # macOS/Linux
> curl -LsSf https://astral.sh/uv/install.sh | sh
> 
> # Windows (PowerShell)
> powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
> ```

### 方法四：手動安裝（傳統方式）

1. 安裝依賴套件：
   ```bash
   pip install pywebview flask flask-sqlalchemy flask-migrate python-dotenv pillow
   ```

2. 啟動應用程式：
   ```bash
   python main.py
   ```

### Linux 額外設定

如果在 Linux 上遇到 GTK 相關錯誤，請安裝系統依賴：

#### Ubuntu/Debian:
```bash
sudo apt-get install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.0
```

#### CentOS/RHEL:
```bash
sudo yum install python3-gobject gtk3-devel webkit2gtk3-devel
```

## 新功能特色

### 🖥️ 桌面應用體驗
- 獨立的桌面視窗，無需瀏覽器
- 原生視窗控制（最小化、最大化、關閉）
- 可調整視窗大小（最小 800x600）
- 適合不同作業系統的原生外觀

### 🚀 效能優化
- 自動端口檢測，避免衝突
- 後台 Flask 服務器管理
- 快速啟動和關閉

### 🔧 技術特點
- 基於 PyWebView 的現代 UI 框架
- Flask 後端提供 REST API
- SQLite 資料庫，無需額外配置
- 支援文件上傳和管理

## 使用指南

### 首次啟動
1. 程式會自動創建資料庫和必要資料夾
2. 預設視窗大小為 1200x800
3. 所有功能與網頁版完全相同

### 資料儲存
- 資料庫文件：`knowledge.db`
- 上傳文件：`uploads/` 資料夾
- 設定文件：`.env`（可選）

### 快捷鍵支援
- `Ctrl+S` / `Cmd+S`：儲存當前表單
- `Ctrl+Enter` / `Cmd+Enter`：快速提交

## 故障排除

### 常見問題

**Q: 視窗無法啟動**
A: 檢查 Python 版本是否為 3.11+，確保所有依賴已正確安裝

**Q: uv 命令找不到**
A: 請先安裝 uv 包管理器，或使用 `run.bat`/`run.sh` 腳本會自動回退到標準 Python 環境

**Q: uv sync 失敗**
A: 確保您在項目根目錄下，並且有 `pyproject.toml` 和 `uv.lock` 文件

**Q: 找不到模組錯誤**
A: 
- 如果使用 uv：運行 `uv sync` 重新同步依賴
- 如果使用 pip：運行 `pip install pywebview flask flask-sqlalchemy flask-migrate python-dotenv pillow`

**Q: Linux 下 GTK 錯誤**
A: 安裝對應的系統 GTK 依賴套件

**Q: macOS 安全性警告**
A: 在系統偏好設定 > 安全性與隱私中允許應用程式運行

**Q: 端口被佔用**
A: 程式會自動尋找可用端口，通常不會有此問題

### 開發模式

如需進行開發或除錯，可以修改 `main.py` 中的設定：

```python
# 開啟除錯模式
webview.start(debug=True)

# 開啟 Flask 除錯模式
app.run(debug=True)
```

#### 使用 uv 進行開發

```bash
# 開發時啟動（帶除錯）
uv run python main.py

# 添加新依賴
uv add package_name

# 更新所有依賴
uv sync --upgrade
```

## 文件結構

```
knowledge_system/
├── main.py              # WebView 啟動器
├── app.py               # Flask 應用主體
├── models.py            # 資料庫模型
├── run.bat              # Windows 智能啟動腳本（支援 uv）
├── run.sh               # macOS/Linux 智能啟動腳本（支援 uv）
├── run_uv.py            # UV 專用啟動器
├── pyproject.toml       # uv 項目配置
├── uv.lock              # uv 依賴鎖定文件
├── templates/           # HTML 模板
├── static/              # 靜態資源
├── migrations/          # 資料庫遷移
├── uploads/             # 上傳文件（自動創建）
└── knowledge.db         # SQLite 資料庫（自動創建）
```

## 版本資訊

- 當前版本：1.0.0
- 支援 uv 包管理器 (推薦)
- 基於 PyWebView 5.0+
- 支援 Flask 3.0+
- 向後兼容標準 pip 環境

## 技術支援

如遇到問題，請檢查：
1. Python 版本是否符合需求
2. 所有依賴是否正確安裝
3. 系統權限是否足夠
4. 防火牆是否阻擋本地連接

---

**享受您的桌面知識管理體驗！** 🎉