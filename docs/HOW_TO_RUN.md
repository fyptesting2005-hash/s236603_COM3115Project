# FinSight 啟動教學 — VS Code 與 Windows CMD

本教學教你把 FinSight 網站跑起來。前後端是**兩個獨立服務**，需要**兩個終端機同時運行**：

| 服務 | 資料夾 | 指令 | 網址 |
|---|---|---|---|
| 後端 API（Python） | `backend/` | `uvicorn app.main:app --port 8000` | http://localhost:8000/docs |
| 前端網站（React） | `frontend/` | `npm run dev` | **http://localhost:5173** ← 網站在這 |

> 網站入口是 **5173**（前端），不是 8000。8000 是 API，主要用來看自動文件。

---

## 事前需求（本機已裝好，僅新電腦需要檢查）

1. **Python 3.10+** — 終端機輸入 `python --version` 有反應即可
2. **Node.js 18+** — 輸入 `node --version` 有反應即可（到 https://nodejs.org 裝 LTS 版）
3. （可選）AI 功能需要 `backend/.env` 內有 Gemini key —— **你的電腦已設定好**，不用動

---

# 方法一：Visual Studio Code（推薦）

### 第 1 步：用 VS Code 開啟專案資料夾

- 開 VS Code → **File → Open Folder...** → 選擇：
  `C:\Users\vicol\Documents\COM3115 Financial Technology\project\finsight`
- 或在檔案總管進入 `finsight` 資料夾後，右鍵 → **Open with Code**

### 第 2 步：開兩個終端機

VS Code 上方選單 → **Terminal → New Terminal**（快速鍵 `Ctrl` + `` ` ``）開出第一個終端機；
再按一次 **Terminal → New Terminal** 右邊的 `+`（或點終端機面板右上角的 `+`）開第二個。
兩個終端機會並排顯示，右側下拉可切換。

### 第 3 步：終端機 A —— 啟動後端

在**第一個**終端機輸入（逐行）：

```bash
cd backend
pip install -r requirements.txt
python warmup.py
uvicorn app.main:app --port 8000
```

| 指令 | 何時需要 | 作用 |
|---|---|---|
| `cd backend` | 每次 | 進入後端資料夾 |
| `pip install -r requirements.txt` | 只需第一次（或換電腦） | 安裝 Python 套件 |
| `python warmup.py` | 只需第一次（或想更新市場數據；需連網） | 下載真實股價到本地快取 + 煙霧測試，應顯示 9 個 `[OK]` |
| `uvicorn app.main:app --port 8000` | 每次 | 啟動後端 API |

看到 `Uvicorn running on http://127.0.0.1:8000` 就是成功。**這個視窗不要關。**

### 第 4 步：終端機 B —— 啟動前端

切到**第二個**終端機輸入：

```bash
cd frontend
npm install
npm run dev
```

| 指令 | 何時需要 | 作用 |
|---|---|---|
| `cd frontend` | 每次 | 進入前端資料夾 |
| `npm install` | 只需第一次 | 安裝 React 套件（幾分鐘） |
| `npm run dev` | 每次 | 啟動網站開發伺服器 |

看到 `Local: http://localhost:5173/` 就是成功。

### 第 5 步：打開網站

瀏覽器（建議 Chrome/Edge）輸入：**http://localhost:5173**

- 完整跑一遍：填問卷 → Generate → View my portfolio → 五個分頁
- API 自動文件：http://localhost:8000/docs

### 第 6 步：關閉

兩個終端機各按 **`Ctrl` + `C`**（可能要按兩次），或直接關掉終端機。

---

# 方法二：Windows CMD（命令提示字元）

原理一樣：開**兩個** CMD 視窗，一個跑後端、一個跑前端。

### 開啟 CMD

按 `Win` + `R` → 輸入 `cmd` → Enter。

### 視窗 1 —— 後端

```bat
cd /d "C:\Users\vicol\Documents\COM3115 Financial Technology\project\finsight\backend"
pip install -r requirements.txt
python warmup.py
uvicorn app.main:app --port 8000
```

> `cd /d` 的 `/d` 不能省——因為專案在 C 槽，`/d` 讓 cd 可以跨磁碟切換。

### 視窗 2 —— 前端（再開一個新 CMD）

```bat
cd /d "C:\Users\vicol\Documents\COM3115 Financial Technology\project\finsight\frontend"
npm install
npm run dev
```

### 打開網站

瀏覽器輸入 **http://localhost:5173**（同方法一）。

### 關閉

兩個視窗各按 `Ctrl` + `C`，或直接關視窗。

---

# 常見問題排解

| 症狀 | 原因 | 解法 |
|---|---|---|
| `'python' 不是內部或外部指令` | Python 不在 PATH | 改試 `py --version`；用 `py -m pip install ...`、`py warmup.py`、`py -m uvicorn app.main:app --port 8000` |
| `'npm' 不是內部或外部指令` | 沒裝 Node.js | 到 https://nodejs.org 安裝 LTS 版後**重開終端機** |
| `WinError 10048` / `EADDRINUSE`（埠被佔用） | 上次的伺服器沒關 | `netstat -ano | findstr :8000` 找 PID → `taskkill /PID <數字> /F`（5173 同理） |
| `warmup.py` 網路錯誤 | 無法連 Yahoo Finance | 沒關係——程式自動改用離線快取 `backend/app/data/prices_snapshot.csv`，網站照常可用 |
| 網站開了但圖表空白 / API error | 後端沒先啟動 | **順序很重要**：先後端（8000），再前端（5173） |
| AI 按鈕顯示 offline fallback | 沒有 Gemini key 或斷網 | 正常降級設計；把 `backend/.env` 的 `GEMINI_API_KEY` 填好即可（本機已填） |
| 防火牆彈窗問「允許存取」 | Python 開本地埠 | 點「允許」（僅私人網路即可，這是本機服務） |

### 順手驗證（可選）

```bat
cd /d "C:\Users\vicol\Documents\COM3115 Financial Technology\project\finsight\backend"
python -m pytest -q
```

應顯示 `69 passed`。

---

## 快速速查卡（貼在便條紙）

```
終端機 1:  cd backend  →  uvicorn app.main:app --port 8000
終端機 2:  cd frontend →  npm run dev
瀏覽器:    http://localhost:5173
關閉:      兩個終端機各 Ctrl+C
```
