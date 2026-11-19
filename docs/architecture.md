# XHotLab 技术架构

## 服务组成

**XHotLab 主服务（127.0.0.1:8766）** 由 FastAPI 提供网页、REST API 和本地任务管理，使用 SQLite 保存热点、创作草稿和发布队列。APScheduler 定期运行 X 中文热点查询、同步 CreatorHub 已有采集任务以及可选图文任务。

**CreatorHub 服务（127.0.0.1:8000）** 是独立安装的上游项目，负责平台账号登录、作品采集与媒体下载。XHotLab 通过 `app/creatorhub_bridge.py` 连接该服务，再由 `app/douyin_pipeline.py` 把抖音候选视频关联至本地发布队列。

**Microsoft Edge 扩展（Manifest V3）** 提供侧边栏、内容脚本和后台 service worker。`edge-extension/localhost-bridge.js` 在本地 XHotLab 页面广播当前浏览器配置的扩展 ID，`web/publish.js` 使用扩展外部消息通道发起发布准备。扩展通过 `edge-extension/background.js` 协调 X 编辑器与媒体上传。

## 发帖准备流程

1. 素材发现：CreatorHub 提供公开作品数据和媒体来源。
2. 文案编辑：用户在 XHotLab 页面手动填写完整正文。
3. 本地媒体准备：按需获取 MP4、校验视频格式与编码，关联发布队列。
4. 浏览器集成：Edge 扩展打开当前浏览器的 X 发帖编辑器并传送文字和媒体。
5. 人工确认：用户在 X 中检查实际内容并点击发布；可返回登记帖子链接。

## 数据与权限

- 项目使用本机 SQLite 数据库和 `data/` 素材目录。它们在 `.gitignore` 内。
- 后台运行日志写入 `logs/`，也由 `.gitignore` 排除。
- AI 功能使用的模型配置和账号凭据按程序设置存放于本地环境；Git 仓库不提交用户的账号信息。
- 外部扩展消息仅从 XHotLab 的本地 Web 来源发起，后台校验消息发送方。
- XHotLab 依赖 CreatorHub、x-lookup 和 ClickClick 等独立项目，各项目保留自己的功能、更新方式和许可证。

## 代码位置

- `app/main.py`：HTTP API、后台任务与网页入口。
- `app/store.py`：SQLite 表结构和数据访问。
- `app/xsource.py`：X 中文公开帖子查询。
- `app/douyin_pipeline.py`：视频候选整理与发布队列关联。
- `app/media.py`：图片和视频本地处理。
- `web/app.js`、`web/publish.js`：网页导航与 X 发布准备界面。
- `edge-extension/`：浏览器侧边栏、扩展服务进程与 X 编辑器交互。

## 自行部署

目前的安装脚本适用于 Windows 10 / 11。默认采用本地回环地址 `127.0.0.1`，服务端口分别为 `8766` 和 `8000`。CreatorHub 路径可通过 `CREATORHUB_HOME` 指定。
