# Yulow｜語落

Windows 全域語音輸入工具。按一下右 `Alt` 開始錄音，再按一下停止；程式會辨識繁體中文、英文、日文及混合內容，並自動輸入到原來的游標位置。

## 目前功能

- 右 Alt 切換開始／停止，並發出不同提示音
- 本機 Whisper 中英日語音辨識，無每日字數限制
- 自動輸入到瀏覽器、LINE、Word、Notion 等目前輸入位置
- 浮動視窗顯示辨識內容
- 一鍵復原剛才的輸入
- 最近記錄與自動統計常用句
- 收藏、查看及再次輸入常用句
- 中文自動轉換為臺灣繁體用字
- 中文、英文、日文的本機 AI 文法校正（可在設定中開關）
- 最小化後常駐系統匣；按右 `Alt` 只顯示小型錄音狀態窗

## 啟用本機 AI 文法校正

語落不需要綁定 API，也不會使用雲端點數。它會把辨識結果交給你電腦上的 Ollama 模型校正，文字不會離開電腦。

1. 從 [Ollama 官方網站](https://ollama.com/download/windows) 安裝 Ollama。
2. 在 Ollama 下載 `qwen3:4b` 模型。
3. 開啟語落的「設定」→「文法校正」，選擇「本機 AI 校正」。

模型只需下載一次；它會占用數 GB 磁碟空間，校正速度取決於電腦效能。若本機 AI 尚未安裝，語落仍可正常語音輸入，並改用安全的標點整理。

第一次開啟語落時，如果偵測不到本機 AI，程式會顯示可略過的安裝引導，並提供 Ollama 官方下載頁連結；使用者也隨時可從「設定」重新開啟此指南。

## 首次使用

1. 雙擊 **安装与启动.bat**。
2. 安裝完成後，把游標放進任何輸入框。
3. 按一下右 `Alt` 開始說話，再按一次停止。
4. 第一次辨識時會下載約 500 MB～1 GB 的模型，之後可以離線使用。

資料保存在 `%LOCALAPPDATA%\TypeListVoice`（沿用舊測試版的位置，以保留記錄），不會上傳到伺服器。

## 開發

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt pytest
.venv\Scripts\python -m pytest
.venv\Scripts\python main.py
```

建立 Windows 壓縮包：

```powershell
.\build.ps1
```
