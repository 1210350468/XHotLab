# XHotLab · 多平台内容运营与 X 发布工作台

## 日常发布

打开 `http://127.0.0.1:8766/`，首页默认显示「发布到 X」。

1. 左侧按真实点赞量选择一条已采集的抖音热门视频。
2. 右侧手动填写 X 发布正文，按输入框内的内容直接发送到编辑器。原作者与来源链接保存在视频素材信息中。
3. 点击「上传视频并打开 X 编辑器」。系统自动关联发布任务、下载并检查 MP4，
   通过当前 Edge 的 XHotLab 扩展打开 X 编辑器、填写文案并上传视频。
4. 在 X 页面确认视频处理完成、账号和文字内容，再点击「发布」。
   完成后可在首页登记实际帖子链接。

采集任务管理、X 热门原帖、图文工厂、历史队列、AI 聊天和模型设置
集中放在左侧「更多工具与管理」。首页只在需要登录平台账号、
刷新 Edge 扩展或修复下载失败时展示对应的操作提示。

网页通过限定为 `http://127.0.0.1:8766` 的扩展外部消息通道，
向已安装的 XHotLab Edge 扩展发送实际发布队列编号；发布信息继续
从本地服务获取，原有账号登录状态保持在当前 Edge 配置中。

## Edge 扩展

### 抖音视频采集与手动 X 发布计划

CreatorHub 已接入真实的抖音登录账号与关键词采集接口。视频采集任务记录
在 CreatorHub 中，XHotLab 通过对应任务 ID 读取原视频链接、作者、正文、
发布时间、点赞和评论，并保存到本机 douyin_video_candidates 数据表。

侧边栏「多平台」中直接展示视频候选及计划时间；点击「进入 X 发布队列」
可手动编辑发布正文，原始抖音作品链接和作者信息保持可查。
一个发布任务支持四张图片或一个 MP4。视频采用 FFprobe 检测
H.264、AAC、分辨率及文件大小，允许的上传上限为 512 MiB。
候选视频可直接通过 CreatorHub 下载 MP4，也可上传本地 MP4；
系统检查视频编码、分辨率和文件大小，Edge 扩展通过持续连接将
MP4 分块传输到当前主窗口的 X 编辑器。原作者和原视频链接随候选记录保留。

真实视频采集、计划状态、编码检测与 Edge 界面测试：

~~~powershell
.\.venv\Scripts\python.exe -m pytest tests\ui_douyin_video_live.py -q -s
~~~

### XHotLab 多平台运营中心

XHotLab 的多平台运营中心从 `http://127.0.0.1:8766/?view=creatorhub` 进入，
当前浏览器标签页直接切换到 `http://127.0.0.1:8000/` 的完整运营页面。
通过主工作台侧栏「多平台运营中心」或 Edge 扩展侧边栏的
「完整工作台」进入。现有账号登录、批量采集、监控、素材管理、发布和互动管理界面
统一展示 XHotLab 品牌。

平台功能基于开源 [CreatorHub](https://github.com/3441293738/creatorhub) 项目，
默认源码位于 XHotLab 同级目录中的 `CreatorHub`，后台运行于 `http://127.0.0.1:8000`。
可通过环境变量 `CREATORHUB_HOME` 指定其他目录。
继续使用原有 SQLite 数据库和账号浏览器环境，保持已登录账号与已采集素材。
运营页面使用相同的品牌标志、紫色视觉体系和清晰的返回入口，点击
「热门内容工作台」即可返回原来的 XHotLab 热点页面。
两个本地服务分别运行，沿用本机访问控制和跨站请求保护。

侧边栏读取抖音、小红书、快手、视频号和 TikTok 的账号数量、
启用中的监控、下载作品和评论统计；显示已登录账号状态。
「读取当前网页」可以导入五个平台作品页面的地址，
「解析作品」和「下载媒体」直接调用 CreatorHub 原有素材接口。
点击「打开 XHotLab 多平台运营中心」可直接进入统一工作台。
侧边栏在用户点击「启动多平台服务」时通过 Windows `pythonw` 启动后台。

真实集成测试：使用项目虚拟环境执行
tests/ui_creatorhub_integration_live.py。

**XHotLab · 中文创作助手 1.2.9** 位于项目内的 `edge-extension` 目录。扩展使用 XHotLab 的 SVG 品牌标志及 16、32、48、128 像素工具栏图标。网页版通过本地桥接程序自动发现当前 Edge 配置内的扩展 ID，扩展侧边栏会核对后台组件版本。

点击 Edge 工具栏的 XHotLab 图标，即可打开右侧中文创作栏，包含五个工作区：

- **热门**：读取最近 24 小时的真实 X 中文原帖，按照动态热度或发布时间排序。
- **当前帖**：读取正在浏览的 X 原帖及图片。X 时间线帖子下方也提供「✦ XHotLab」按钮，直接采集该帖子。
- **图文**：调用 Zen 生成原创中文观点，使用 ClickClick 制作三张配图，复用之前保存的素材包。
- **发布**：编辑文案、预览原帖图片与原创图卡，最多选择四张图片；支持选择本地文件和拖入图片，上传后自动加入发布队列。
- **多平台**：展示 CreatorHub 五个平台，管理抖音视频候选、手动文案、MP4 素材下载与发布排程。

品牌图标源文件为 `web/brand.svg`、`edge-extension/brand.svg`。当前本机
CreatorHub 的品牌图标位于其 `app/web/brand.svg`。扩展图标由
`tools/export_brand_assets.py` 通过 Playwright 与 Pillow 导出。

点击「在当前 Edge 主窗口准备发布」时，扩展连接已登录 X 的标签页，填写文案并附加图片或 MP4。上传步骤和异常原因显示在侧边栏；用户在 X 编辑器检查内容并确认发布。

扩展使用本机 127.0.0.1:8766 的现有 FastAPI 服务、SQLite 数据库和 Windows 无窗口定时任务。Zen 密钥继续保存在 Windows 凭据管理器。

需要在其他 Edge 配置中安装时，打开 `edge://extensions/`，启用开发人员模式，点击「加载解压缩的扩展」，选择项目中的 `edge-extension` 文件夹。

### 扩展验证命令

~~~powershell
.\.venv\Scripts\python.exe tests\ui_edge_extension_live.py
.\.venv\Scripts\python.exe tests\ui_edge_extension_upload_live.py
node --check edge-extension\background.js
node --check edge-extension\content.js
node --check edge-extension\sidepanel.js
~~~

本地 Windows 工作台：发现 X 中文区热门原帖，结合真实互动数据筛选讨论，使用 OpenCode Zen 生成原创中文观点和三张配图，并准备在 X 官方编辑器中发布。

**本地地址**：<http://127.0.0.1:8766>

## 已接入的开源项目

- [x-lookup](https://github.com/mynameistito/x-lookup)：公开 X 帖子搜索服务。接收真实中文帖子正文、发布时间、原作者、原帖链接、点赞、转发、回复和浏览数据。使用免费只读搜索接口，不需要 X 开发者 API 密钥。
- x-lookup 的 media.all 字段提供原帖图片、视频封面、尺寸和来源地址。XHotLab 会将选定话题的图片保存到独立的 data/source_media 素材库。
- [ClickClick](https://github.com/mintyPT/clickclick)：使用 Playwright 和网页模板生成 PNG 社交图片。每个话题生成 3 张 900×1200 图卡。
- FastAPI、SQLite、APScheduler：工作台、持久化存储和计划任务。
- OpenCode Console Zen：中文写稿及聊天模型，可选择模型、思考强度并查看费用。
- Codex 与 Claude Code：在本机执行得到明确授权的分析和文件操作任务。

## X 中文热门发现

后台每 15 分钟采集一次 X 中文区公开原帖，页面每 3 分钟静默更新。默认展示最近 24 小时的帖子；过期帖退出热门列表，已保存的历史原帖、草稿及图文素材保留在数据库与素材目录。实时热度根据真实互动分数和发布时间动态衰减，帖子越旧热度权重越低。

每次搜索只读取 X 中文区的公开原帖：

- 热门讨论：最近 24 小时内、互动较高的中文内容
- AI 与科技
- 游戏与影视
- 生活与趣事
- 数码与互联网

使用原帖点赞、转发、回复、浏览量和发布时间计算选题热度。过滤抽奖、推广、短文、敏感媒体等内容。每个候选内容均保留真实 X 原帖地址。发现与创作共用 X 数据，页面和图文工厂显示同一来源。

## 自动图文创作

北京时间 **09:00、14:00、20:00** 自动执行。每次生成两个话题，每日记录模型费用达到 $0.20 时停止继续生成。

每套包含：

- 原作者、原帖链接与互动数据
- 原帖照片和视频封面，带来源记录
- 一段重新组织、包含独立观点的中文 X 草稿
- `cover.png`、`context.png`、`discussion.png` 三张原创图文卡片
- `card.json`、`post.txt` 和 ZIP 素材包
- 草稿箱记录和待发布队列记录

图文素材位于 `data/generated/<原帖哈希>/`。点击工作台「自动图文工厂」可以检查和下载每一套。

## X 网页发布

在「待发布队列」中可以查看 AI 原创图片及 X 原帖媒体，勾选最多四张图片并保存到本地数据库。「选择原创三图」可恢复默认原创配图。

点击「导入 X 原帖图片」下载真实照片和视频封面。原帖素材标明原作者与来源链接，使用其他创作者的媒体文件前应确认相应使用许可。

Edge 扩展使用当前已登录的主窗口执行发布准备。网页版继续提供历史发布任务和素材包管理入口。

同时保留「打开 X 发帖窗口」预填文字的入口，以及下载所选图片、文案和来源记录的 ZIP 素材包。

X 官方自动化规则限制以网页脚本批量自动发布热点内容。浏览器助手用于准备文字和图片，最终发布需由账号持有人在 X 编辑器确认。

相关接口：GET /api/trends/{id}/media、GET /api/queue/{id}/media、PUT /api/queue/{id}/media、POST /api/queue/{id}/media/import、GET /api/queue/{id}/bundle、POST /api/queue/{id}/prepare-browser、GET /api/queue/{id}/browser-preparation。

## 安装与启动

在 Windows 10/11 上安装 Python 3.12、Git for Windows、Node.js LTS、FFmpeg（包含 `ffmpeg.exe` 和 `ffprobe.exe`）以及 Microsoft Edge。将 FFmpeg 所在文件夹加入 `PATH`。

从 GitHub 克隆 XHotLab 后，在 PowerShell 中进入克隆得到的目录，执行：

```powershell
.\install.ps1
.\start.ps1
```

`install.ps1` 会在同级目录获取 CreatorHub 原版源码，并安装两套 Python 环境、CreatorHub 浏览器组件及图文依赖。`start.ps1` 检查 XHotLab 与 CreatorHub 的实际健康状态后启动后台服务。

访问 <http://127.0.0.1:8766>。打开 `edge://extensions/`，加载项目中的 `edge-extension` 目录。发布页面会自动识别这个 Edge 配置里的插件。首次使用 X 或抖音采集功能时，分别登录自己的平台账号。

可自行执行 `./install_startup.ps1` 注册登录 Windows 时自动启动的计划任务。后台日志位于 `logs/server.stdout.log` 和 `logs/server.stderr.log`。

**GitHub 分享范围：** 版本库包含 `app/`、`web/`、`edge-extension/`、`integrations/`、`scripts/`、`tools/`、`tests/` 以及安装脚本和文档。`.gitignore` 排除数据库、API 密钥、浏览器会话、已下载媒体、日志和本机虚拟环境。每位使用者在自己电脑上独立登录 X、抖音等平台。

项目依赖的 CreatorHub 原版仓库由安装脚本获取。你当前电脑的 CreatorHub 页面包含额外的 XHotLab 品牌调整；克隆上游原版的朋友会看到 CreatorHub 原始界面。相关品牌改动可以作为独立维护的 CreatorHub 仓库分享。

OpenCode Zen API 密钥保存在 Windows 凭据管理器。通过网页右上角模型设置连接，支持官方模型目录及思考强度。

## 命令行

```powershell
.\.venv\Scripts\python.exe -m app.cli scan
.\.venv\Scripts\python.exe -m app.cli hot --count 15
.\.venv\Scripts\python.exe -m app.cli creative-run --count 2 --refresh
.\.venv\Scripts\python.exe -m app.cli creative-packs
.\.venv\Scripts\python.exe -m app.cli creative-status
.\.venv\Scripts\python.exe -m app.cli queue
```

Agent 工具可使用上述命令，或访问本机的 `/api/trends`、`/api/creative/status`、`/api/creative/run`、`/api/creative/packs`、`/api/queue` 等接口。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe tests\smoke_live.py
.\.venv\Scripts\python.exe tests\smoke_zen_live.py
.\.venv\Scripts\python.exe tests\ui_live.py
.\.venv\Scripts\python.exe tests\ui_zen_live.py
.\.venv\Scripts\python.exe tests\ui_creative_live.py
node --check web\app.js
node --check web\creative.js
```
