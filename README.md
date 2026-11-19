<div align="center">

<img src="docs/assets/xhotlab-cover.svg" width="100%" alt="XHotLab 项目封面：发现 X 中文热点、整理视频素材、手动编写文案并打开 X 编辑器" />

# XHotLab

### 开源 X / Twitter 热点发现与内容发布工作台

**Discover trends · Organize media · Prepare posts for X**

Windows 本地运行｜Microsoft Edge 扩展｜中文热点发现｜短视频素材整理｜人工确认发布

[![Windows](https://img.shields.io/badge/Windows-10%20%2F%2011-4869ed?style=flat-square)](docs/getting-started.md)
[![Python](https://img.shields.io/badge/Python-3.12-3776ab?style=flat-square)](requirements.txt)
[![Edge](https://img.shields.io/badge/Browser-Microsoft%20Edge-20a4a4?style=flat-square)](edge-extension/)
[![License: MIT](https://img.shields.io/badge/License-MIT-7358e6?style=flat-square)](LICENSE)

[**🌐 在线展示**](https://1210350468.github.io/XHotLab/) · [**🚀 快速开始**](#-快速开始) · [**📸 界面展示**](#-真实界面展示) · [**📖 使用指南**](docs/getting-started.md) · [**❓ 常见问题**](docs/faq.md) · [**English**](#-english-overview)

</div>

XHotLab 是一个面向中文创作者的本地内容运营工具。它将 X（原 Twitter）中文热点发现、CreatorHub 多平台素材采集、发布队列和 Edge 浏览器发帖准备流程集中在一个界面中。用户选择素材、自己写正文，系统负责整理 MP4 / 图片并将内容送入 X 官方编辑器，由用户确认后发布。

## ✨ 能做什么

- **发现 X 中文热点**：读取公开 X 帖子的正文、时间、互动量和来源链接，按分类与热度浏览。
- **从热门视频挑选素材**：通过 [CreatorHub](https://github.com/3441293738/creatorhub) 采集抖音作品信息，并保留作者、原视频地址、点赞和评论数据。
- **手动编写发布文案**：编辑框保持由你控制，提交正文与输入内容一致，支持 280 字长度检查。
- **准备 X 视频与图片发布**：本地检查视频格式、管理发布队列，通过 Microsoft Edge 扩展把媒体与正文送到 X 发帖编辑器。
- **扩展创作工作流程**：包括原创图文、草稿管理、热点浏览、多平台运营、AI 聊天和模型设置，按需展开。
- **本地数据与账号管理**：SQLite 和素材保存在用户电脑中，各平台账号在用户自己的浏览器环境中登录。

## 📸 真实界面展示

### 01 · 一个页面完成视频选题与发帖准备

![XHotLab 视频发布工作台的实际运行截图，左侧为热门视频列表，右侧为手动文案与 X 编辑器准备入口](docs/assets/publish-workbench.png)

### 02 · 浏览真实 X 中文热门讨论

![XHotLab 热点发现页面实际截图，包含分类、实时热度、搜索和公开帖子的互动数据](docs/assets/trends-discovery.png)

### 03 · Edge 侧边栏，随时查看与准备发布

<img src="docs/assets/edge-sidepanel.png" width="400" alt="XHotLab Microsoft Edge 扩展侧边栏实际截图：热门、当前帖、图文、发布、多平台五个入口" />

<sub>截图来自实际运行的本地工作台，第三方视频封面、作者等部分区域已做隐私处理。操作流程需要用户自行登录对应平台。</sub>

## 🚀 快速开始

**系统要求**：Windows 10 / 11、Python 3.12、Git for Windows、Node.js LTS、FFmpeg（含 FFprobe）、Microsoft Edge。

在 PowerShell 中执行：

```powershell
git clone https://github.com/1210350468/XHotLab.git
cd XHotLab
.\install.ps1
.\start.ps1
```

打开 **http://127.0.0.1:8766**，进入「发布到 X」工作台。打开 `edge://extensions`，启用开发人员模式，选择「加载解压缩的扩展」，安装项目内的 `edge-extension` 文件夹。

安装脚本会获取并安装依赖的 CreatorHub 原版项目。多平台采集功能需要用户在 CreatorHub 登录自己的平台账号。FFmpeg 用于 MP4 格式检查与视频准备。

**[详细安装说明、常见故障与命令行操作](docs/getting-started.md)**

## 🎬 三步准备一条 X 帖子

1. **选择素材**：在首页点击已经采集的热门视频，或者通过「更多工具与管理」进入热门发现、采集和草稿页面。
2. **填写正文**：手动输入准备发布的完整文字，选择视频或图片，检查素材来源信息。
3. **打开 X 编辑器**：点击上传与准备按钮，由 Edge 扩展打开当前浏览器的 X 编辑器，检查上传状态和文字，随后由用户点击「发布」。

XHotLab 支持在完成发布后登记实际 X 帖子链接，便于区分待发布、已打开和已完成的任务。

## 🧩 项目组成

- **FastAPI + SQLite + APScheduler**：本地工作台、数据管理和定时任务。
- **Microsoft Edge Manifest V3 扩展**：热点侧边栏、当前 X 页面内容读取、图文和视频上传准备。
- **CreatorHub（独立依赖）**：抖音、小红书、快手、视频号和 TikTok 的账号与素材运营功能。
- **x-lookup（第三方服务）**：X 中文公开帖子搜索。
- **ClickClick 与可选的 OpenCode Zen**：图文渲染、模型辅助功能。

安装、运行目录、数据保存位置和安全边界详见 [技术架构](docs/architecture.md)。

## ❓ 常见问题

**能直接把抖音视频发布到 X / Twitter 吗？** 采集、下载和视频准备功能由 CreatorHub 与 XHotLab 配合完成。Edge 扩展在 X 编辑器中填写文字与媒体，发布按钮由用户本人确认。

**为什么要安装 Edge 扩展？** 视频文件和文案需要在已经登录 X 的本机浏览器中填写。XHotLab 会自动识别当前浏览器配置中的扩展 ID。

**会自动给视频添加作者或生成尴尬的文案吗？** 首页采用完整手写正文，系统保留作者和来源记录以便核对，不会向输入内容添加固定格式的作者署名。

**支持哪些操作系统？** 当前安装与启动脚本面向 Windows 10 / 11，浏览器集成以 Microsoft Edge 为目标。

更多关于安装、登录、视频编码、数据保存和 CreatorHub 的问题，请查看 [常见问题 FAQ](docs/faq.md)。

## 🌍 English overview

**XHotLab is a self-hosted Windows content discovery and X (Twitter) publishing assistant.** It combines Chinese X trend discovery, a CreatorHub-powered cross-platform media workflow, a local publishing queue, and a Microsoft Edge extension for preparing posts in the official X composer.

**Use cases:** Discover Chinese-language trending posts on X, organize public short-video leads from Douyin, write your own caption, inspect MP4 assets, and prepare an X post in your signed-in Edge browser. The account owner reviews and submits the final post.

**Keywords:** X Twitter publishing assistant, local social media workflow, Douyin to X content preparation, Chinese Twitter trends, Microsoft Edge extension, self-hosted content studio, CreatorHub integration, video publishing queue.

Read the [English setup and product description](docs/getting-started.md) and [FAQ](docs/faq.md) for details.

## 🤝 开源与贡献

欢迎反馈实际问题、讨论功能与提交 Pull Request。提出问题时请说明 Windows、Edge、Python 版本和可复现的操作步骤，日志中请自行隐藏账号令牌与隐私内容。

XHotLab 自有源码以 [MIT License](LICENSE) 发布。CreatorHub、x-lookup、ClickClick 和其他依赖遵循各自的项目许可证。此仓库不会包含个人浏览器会话、平台账号、下载视频或本地数据库。

**项目主页：** https://1210350468.github.io/XHotLab/ · **GitHub：** https://github.com/1210350468/XHotLab
