# XHotLab 安装与使用指南 / Getting started

**项目地址：** https://github.com/1210350468/XHotLab
**本地页面：** http://127.0.0.1:8766

XHotLab 在 Windows 电脑上运行 FastAPI 服务，通过 Microsoft Edge 扩展连接已登录的 X 帐号；需要短视频采集时再启用独立的 CreatorHub 服务。

## 运行环境

- Windows 10 或 Windows 11；Microsoft Edge。
- Python 3.12 和 Windows Python Launcher `py`。
- Git for Windows。
- Node.js LTS 与 npm。
- FFmpeg 和 FFprobe，并确保 PowerShell 中可以调用 `ffmpeg`、`ffprobe`。
- 创作者自己登录的 X 账号。跨平台采集还需要所对应的平台账号。

## 从 GitHub 安装

打开 Windows PowerShell：

```powershell
git clone https://github.com/1210350468/XHotLab.git
cd XHotLab
.\install.ps1
.\start.ps1
```

`install.ps1` 安装 XHotLab 的 Python / Node.js 依赖，并通过 Git 获取 CreatorHub 原版，通常保存于 XHotLab 同级的 `CreatorHub` 文件夹。可使用环境变量 `CREATORHUB_HOME` 指定其他目录。CreatorHub 安装阶段会安装自身依赖与浏览器组件。

打开 `http://127.0.0.1:8766/`，主页将直接显示「发布到 X」。第一次进入时，视频列表可为空。此时点击页面的采集提示，进入 CreatorHub 配置账号及关键词采集任务。

## 安装 Microsoft Edge 扩展

1. 在 Edge 地址栏打开 `edge://extensions`。
2. 启用「开发人员模式」。
3. 选择「加载解压缩的扩展」，打开 XHotLab 项目内的 `edge-extension` 文件夹。
4. 点击浏览器工具栏中的 XHotLab 图标，打开侧边栏。
5. 在当前 Edge 中登录 X，返回 XHotLab 网页开始准备帖子。

扩展 ID 由浏览器分配。网页版通过本地消息桥接程序识别正在运行的扩展。

## 手动发布一条视频

1. 在「发布到 X」页面选择已经采集的视频。
2. 在「发布到 X 的正文」文本框中自行填写完整正文。
3. 点击「上传视频并打开 X 编辑器」。若素材尚未缓存，本地服务会从 CreatorHub 获取视频并用 FFprobe 检查编码。
4. 在当前 Edge 的 X 编辑器中核对文字、MP4 和当前账号。点击 X 网站的「发布」。
5. 发布完成后可将实际 X 帖子链接登记到工作台。

## 其他功能

左侧「更多工具与管理」包括：X 中文热门讨论、AI 与科技、游戏与影视、生活与趣事、数码与互联网、图文工厂、草稿、历史发布队列、CreatorHub 多平台运营、AI 聊天和模型设置。

图文生成使用 OpenCode Zen 相关设置；手动编写 X 发布正文无需调用模型。

## 路径和服务

- `http://127.0.0.1:8766/`：XHotLab 主工作台。
- `http://127.0.0.1:8000/`：CreatorHub 独立服务。
- `data/`：XHotLab SQLite 数据库、已下载媒体与本地浏览器运行文件。
- `logs/`：XHotLab 后台运行日志。
- `edge-extension/`：Microsoft Edge 浏览器扩展。
- `integrations/`：图文渲染需要的 Node.js 组件。

## 检查安装

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe tests\ui_publish_live.py
.\.venv\Scripts\python.exe tests\ui_edge_extension_live.py
```

浏览器测试会启动独立的 Edge 测试配置。测试通过表示相应的本地工作流和扩展通信可用。实际发布到 X 时，网站的登录状态、媒体处理及账号限制由当前浏览器会话决定。

## English quick start

XHotLab is a **Windows-based, self-hosted X / Twitter content discovery and publishing preparation tool**. Install Python 3.12, Git for Windows, Node.js LTS, FFmpeg / FFprobe, and Microsoft Edge. Clone this repository, then run `./install.ps1` and `./start.ps1` in Windows PowerShell. Open `http://127.0.0.1:8766/`, and load the unpacked extension from `edge-extension/` through `edge://extensions`.

The local UI supports Chinese X trend discovery, media workflows integrated with CreatorHub, manual caption entry, and preparing images or MP4 files for the official X composer. Publishing is confirmed by the account owner in their browser.
