# XHotLab FAQ · 常见问题

**项目主页**：[XHotLab on GitHub](https://github.com/1210350468/XHotLab)
**安装指南**：[Getting started](getting-started.md)

### XHotLab 是什么？

XHotLab 是 Windows 本地运行的开源 X / Twitter 内容发现与发布准备工作台。它提供中文热门帖子浏览、短视频素材选择、手动文案编辑、发布队列和 Microsoft Edge 扩展。

### XHotLab 怎么把抖音视频发到 X / Twitter？

CreatorHub 负责采集作品与下载素材。XHotLab 根据用户选中的视频创建发布队列、检查 MP4 文件并连接 Edge 扩展。扩展在已登录的 X 编辑器中准备文字与视频，由账号持有人核对并点击发布。

### XHotLab 会自动生成 X 文案吗？

首页「发布到 X」使用手动输入的完整正文。系统不会按固定模板附加作者、链接或自动生成的视频点评。作者昵称与来源链接保留在素材记录中，便于用户自己核对。

### XHotLab 需要 Twitter / X API 密钥吗？

XHotLab 的网页热点功能读取第三方公开帖子搜索结果；Edge 发布准备过程使用用户当前登录的 X 网页会话。AI 图文功能使用可选模型配置。具体可用性取决于这些服务及浏览器会话的实际状态。

### 需要安装哪些软件？

当前需要 Windows 10 / 11、Python 3.12、Git for Windows、Node.js LTS、FFmpeg / FFprobe 和 Microsoft Edge。克隆仓库后执行 `install.ps1` 安装依赖，再执行 `start.ps1` 启动服务。

### 可以在 Chrome、macOS 或 Linux 上运行吗？

当前发行版的安装脚本、系统任务和浏览器测试面向 Windows 与 Microsoft Edge。浏览器扩展使用 Chromium Manifest V3，跨平台安装与完整发帖流程尚需对应系统的实机验证。

### CreatorHub 和 XHotLab 有什么关系？

CreatorHub 是独立的多平台采集和运营项目，覆盖抖音、小红书、快手、视频号与 TikTok。XHotLab 将其采集的公开短视频信息和媒体连接到 X 发布准备工作台。安装脚本从 CreatorHub 上游仓库获取项目。

### 视频保存在什么位置？

CreatorHub 在其自身数据目录保存采集作品，XHotLab 把已准备的 MP4 保存到本地 `data/source_videos/`。项目 Git 仓库排除个人视频文件、数据库、日志和浏览器会话。

### 为什么 Edge 插件提示无法连接？

检查 `http://127.0.0.1:8766/` 能否打开，以及 `edge://extensions` 中 XHotLab 扩展是否启用。更新项目后刷新扩展，再使用同一个 Edge 浏览器配置打开 XHotLab 网页与 X 网站。

### Does XHotLab automatically post on X?

XHotLab prepares media and text in the official X composer through a local Microsoft Edge extension. The signed-in account owner reviews the content and submits the final post.

### Is XHotLab a self-hosted social media publishing tool?

Yes. XHotLab runs locally on Windows, stores publishing queue data and downloaded media on the user's computer, and uses a browser extension for X composer preparation. Its separate CreatorHub dependency provides multi-platform collection workflows.

### Can I discover Chinese Twitter trends without purchasing an X API subscription?

XHotLab uses a third-party public X search source for Chinese-language trending-post discovery and presents engagement and source links. The availability of results depends on that source. Preparation of a post in the Edge browser uses the signed-in X website.
