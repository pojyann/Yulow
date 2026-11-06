# Yulow｜語落

Windows 全局语音输入工具。按一下右 `Alt` 开始录音，再按一下停止；程序会辨识繁体中文、英文、日文及混合内容，并自动输入到原来的光标位置。

## 目前功能

- 右 Alt 切换开始／停止，并发出不同提示音
- 本机 Whisper 中英日语音辨识，无每日字数限制
- 自动输入到浏览器、LINE、Word、Notion 等当前输入位置
- 浮动视窗显示辨识内容
- 一键复原刚才的输入
- 最近记录与自动统计常用句
- 收藏、查看及再次输入常用句
- 中文自动转换为台湾繁体用字
- 英文与日文安全标点整理
- 最小化后常驻系统匣；按右 `Alt` 只显示小型录音状态窗

> 完整的英文／日文 AI 文法改写仍在开发中。目前版本只做不会改变原意的标点与空格整理。

## 首次使用

1. 双击 **安装与启动.bat**。
2. 安装完成后，把光标放进任何输入框。
3. 按一下右 `Alt` 开始说话，再按一次停止。
4. 第一次辨识时会下载约 500 MB～1 GB 的模型，之后可以离线使用。

資料保存在 `%LOCALAPPDATA%\TypeListVoice`（沿用舊測試版的位置，以保留記錄），不會上傳到伺服器。

## 开发

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt pytest
.venv\Scripts\python -m pytest
.venv\Scripts\python main.py
```

建立 Windows 压缩包：

```powershell
.\build.ps1
```
