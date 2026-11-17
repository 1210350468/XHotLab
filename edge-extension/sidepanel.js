const API = "http://127.0.0.1:8766";
const state = {
  view: "trends",
  trends: [],
  packs: [],
  queue: [],
  chosenTrend: null,
  chosenQueueId: null,
  currentPost: null,
  creatorhub: null,
  creatorhubDashboard: null,
  creatorhubActivity: null,
  douyinVideos: [],
  busy: false
};

const byId = (name) => document.getElementById(name);

function element(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function append(parent, ...children) {
  parent.append(...children.filter(Boolean));
  return parent;
}

function setNotice(text, error = false) {
  const status = byId("notice");
  status.textContent = text;
  status.classList.toggle("error", error);
}

async function request(path, init = {}) {
  const headers = {...init.headers};
  if (init.method && init.method !== "GET") {
    headers["X-XHotLab-Action"] = "1";
  }
  if (init.body && !(init.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(API + path, {
    ...init,
    cache: "no-store",
    headers
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error(typeof body.detail === "string" ? body.detail :
      "本地服务返回错误 HTTP " + response.status);
  }
  return body;
}

async function perform(button, operation) {
  if (state.busy) return;
  state.busy = true;
  const label = button?.textContent;
  if (button) {
    button.disabled = true;
    button.textContent = "正在执行…";
  }
  try {
    await operation();
  } catch (error) {
    console.error("XHotLab 操作失败", error);
    setNotice(error.message, true);
  } finally {
    state.busy = false;
    if (button) {
      button.disabled = false;
      button.textContent = label;
    }
  }
}

function actionButton(title, operation, style = "secondary") {
  const button = element("button", "button " + style, title);
  button.type = "button";
  button.addEventListener("click", () => perform(button, operation));
  return button;
}

function imageUrl(value) {
  const url = new URL(value, API);
  if (url.origin === API &&
      /^\/(generated|source-media|source-videos|user-media)\//.test(url.pathname)) {
    return url.href;
  }
  if (url.protocol === "https:" && url.hostname === "pbs.twimg.com") {
    return url.href;
  }
  throw new Error("图片地址来源无效");
}

function externalLink(label, url) {
  const parsed = new URL(url);
  if (parsed.protocol !== "https:" || parsed.hostname !== "x.com") {
    throw new Error("X 原帖链接无效");
  }
  const link = element("a", "card-source", label);
  link.href = parsed.href;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  return link;
}

function showImages(parent, choices, className = "mini-media") {
  const items = choices.filter((value) => value?.url).slice(0, 6);
  if (!items.length) return;
  const gallery = element("div", className);
  for (const entry of items) {
    const img = element("img");
    img.src = imageUrl(entry.url);
    img.alt = entry.label || "原帖图片";
    img.loading = "lazy";
    gallery.append(img);
  }
  parent.append(gallery);
}

function age(time) {
  if (!time) return "未知时间";
  const elapsed = Math.max(0, Date.now() - Date.parse(time));
  if (!Number.isFinite(elapsed)) return "未知时间";
  const minutes = Math.floor(elapsed / 60000);
  if (minutes < 60) return minutes + " 分钟前";
  if (minutes < 1440) return Math.floor(minutes / 60) + " 小时前";
  return Math.floor(minutes / 1440) + " 天前";
}

async function switchView(view) {
  state.view = view;
  for (const tab of document.querySelectorAll(".tab")) {
    tab.classList.toggle("active", tab.dataset.view === view);
  }
  for (const section of document.querySelectorAll(".view")) {
    section.classList.toggle("hidden", section.id !== "view-" + view);
  }
  if (view === "trends") return renderTrends();
  if (view === "current") return renderCurrent();
  if (view === "studio") return refreshStudio();
  if (view === "queue") return refreshQueue();
  if (view === "channels") return refreshChannels();
}

const CREATORHUB_PLATFORM_NAMES = {
  douyin: "抖音", xhs: "小红书", kuaishou: "快手",
  shipinhao: "视频号", tiktok: "TikTok"
};

async function openCreatorHub() {
  const info = state.creatorhub || await request("/api/creatorhub/status");
  if (!info.running) throw new Error("请先启动 XHotLab 多平台服务");
  await chrome.tabs.create({url: API + "/?view=creatorhub", active: true});
}

async function refreshChannels() {
  const [status, candidates] = await Promise.all([
    request("/api/creatorhub/status"),
    request("/api/douyin/videos")
  ]);
  state.creatorhub = status;
  state.douyinVideos = candidates;
  if (status.running) {
    const [dashboard, activity] = await Promise.all([
      request("/api/creatorhub/dashboard"),
      request("/api/creatorhub/activity")
    ]);
    state.creatorhubDashboard = dashboard;
    state.creatorhubActivity = activity;
  } else {
    state.creatorhubDashboard = null;
    state.creatorhubActivity = null;
  }
  if (state.view === "channels") renderChannels();
}

function renderCreatorHubShareAccounts() {
  const select = byId("creatorhub-share-account");
  if (!select) return;
  const previous = select.value;
  const accounts = state.creatorhubDashboard?.accounts || [];
  const eligible = accounts.filter((account) =>
    account.status === "active" && account.read_logged_in &&
    !(account.platform === "douyin" && account.risk_status &&
      account.risk_status !== "normal"));
  select.replaceChildren();
  const automatic = element("option", "", "自动选择匹配账号");
  automatic.value = "";
  select.append(automatic);
  for (const account of accounts) {
    const platform = CREATORHUB_PLATFORM_NAMES[account.platform] || account.platform;
    const stateLabel = account.status !== "active" ? "账号不可用" :
      (account.read_logged_in ? "作品读取已登录" : "作品读取待登录");
    const riskLabel = account.platform === "douyin" ?
      " · " + (account.risk_status_label || "风险状态未知") : "";
    const option = element("option", "",
      platform + " · " + account.nickname + " · " + stateLabel + riskLabel);
    option.value = String(account.id);
    option.disabled = account.status !== "active" || !account.read_logged_in ||
      (account.platform === "douyin" && account.risk_status &&
       account.risk_status !== "normal");
    select.append(option);
  }
  if (eligible.some((account) => String(account.id) === previous)) {
    select.value = previous;
  } else if (eligible.length === 1) {
    select.value = String(eligible[0].id);
  } else {
    select.value = "";
  }
}

function renderDouyinCandidates() {
  const parent = byId("douyin-candidates");
  parent.replaceChildren();
  if (!state.douyinVideos.length) {
    parent.append(element("div", "placeholder",
      "CreatorHub 完成关键词采集后，点击「读取抖音采集结果」。"));
    return;
  }
  for (const video of state.douyinVideos) {
    const card = element("article", "card");
    append(card,
      element("p", "card-sub",
        "抖音 @" + video.author_name + " · ♥ " +
        video.like_count + " · 评论 " + video.comment_count),
      element("p", "card-text", video.description)
    );
    if (video.cover_url) {
      const cover = element("img", "douyin-preview");
      cover.src = video.cover_url;
      cover.loading = "lazy";
      cover.alt = "抖音原视频封面";
      card.append(cover);
    }
    const douyinAccount = (state.creatorhubDashboard?.accounts || []).find(
      (account) => account.platform === "douyin");
    const riskBlocked = Boolean(douyinAccount && (
      douyinAccount.manual_review_required ||
      (douyinAccount.risk_status && douyinAccount.risk_status !== "normal")));
    const hasVideo = Boolean(video.video_file);
    if (video.scheduled_at) {
      const timePassed = Date.parse(video.scheduled_at) <= Date.now() &&
        (video.queue_status === "queued" || video.queue_status === "opened");
      const due = timePassed && hasVideo;
      card.append(element("p", "info-line",
        (due ? "已到发布窗口：" :
          (timePassed ? "原计划时间已过，素材尚未就绪：" : "计划发布时间：")) +
        new Date(video.scheduled_at)
          .toLocaleString("zh-CN", {timeZone: "Asia/Shanghai",
            year: "numeric", month: "2-digit", day: "2-digit",
            hour: "2-digit", minute: "2-digit"}) + "（北京时间）"));
    }
    if (douyinAccount && douyinAccount.risk_status &&
        douyinAccount.risk_status !== "normal") {
      card.append(element("p", "info-line",
        "抖音账号状态：" + (douyinAccount.risk_status_label || "暂不可采集") +
        (douyinAccount.risk_reason ? " · " + douyinAccount.risk_reason : "")));
    }
    card.append(element("p", "info-line",
      hasVideo ? "MP4 已下载并登记" :
        (riskBlocked ? "MP4 下载暂停：账号需要处理平台风险状态" :
          "MP4 等待下载")));
    const actions = element("div", "card-actions");
    append(actions, actionButton("查看抖音原视频", () =>
      chrome.tabs.create({url: video.source_url, active: true})));
    if (video.queue_id) {
      actions.append(actionButton("进入 X 发布队列", async () => {
        state.chosenQueueId = video.queue_id;
        await switchView("queue");
      }, "primary"));
    }
    if (video.queue_id && !hasVideo) {
      const download = actionButton("下载 MP4 并加入发布队列", async () => {
        setNotice("CreatorHub 正在读取原视频并下载 MP4…");
        await request("/api/douyin/videos/" +
          encodeURIComponent(video.id) + "/download", {method: "POST"});
        await refreshChannels();
        await refreshQueue();
        setNotice("MP4 已下载并添加到 X 发布队列");
      }, "primary");
      download.disabled = riskBlocked;
      actions.append(download);
    }
    card.append(actions);
    parent.append(card);
  }
}

function renderChannels() {
  const connection = byId("creatorhub-connection");
  const platforms = byId("creatorhub-platforms");
  const accounts = byId("creatorhub-accounts");
  const activity = byId("creatorhub-activity");
  renderDouyinCandidates();
  renderCreatorHubShareAccounts();
  connection.replaceChildren();
  platforms.replaceChildren();
  accounts.replaceChildren();
  activity.replaceChildren();
  const info = state.creatorhub;
  if (!info) {
    connection.append(element("div", "placeholder", "正在读取多平台服务状态"));
    return;
  }

  append(connection,
    element("h3", "card-title", "XHotLab · 本地多平台服务"),
    element("p", "card-text",
      info.running ? "● 服务正常运行 · 账号、媒体与任务保存在本机" :
      (info.installed ? "○ 服务尚未启动" : "尚未安装 CreatorHub 独立运行环境"))
  );
  const buttons = element("div", "card-actions");
  if (!info.running && info.installed) {
    buttons.append(actionButton("启动多平台服务", async () => {
      await request("/api/creatorhub/start", {method: "POST"});
      for (let attempt = 0; attempt < 30; attempt++) {
        await new Promise((resolve) => setTimeout(resolve, 900));
        const result = await request("/api/creatorhub/status");
        if (result.running) {
          await refreshChannels();
          setNotice("CreatorHub 多平台管理服务已启动");
          return;
        }
      }
      throw new Error("CreatorHub 启动异常，请检查本机服务日志");
    }, "primary"));
  }
  if (info.running) {
    buttons.append(actionButton("打开 XHotLab 多平台运营中心 ↗", openCreatorHub, "primary"));
  }
  append(buttons, element("span", "tag",
    info.installed ? "本机已安装" : "等待安装"));
  connection.append(buttons);

  if (!info.running) {
    platforms.append(element("div", "placeholder",
      "启动 CreatorHub 后，可查看五个平台的账号、监控、素材与互动统计。"));
    accounts.replaceChildren();
    activity.append(element("div", "placeholder", "启动后显示真实任务记录。"));
    return;
  }

  const dashboard = state.creatorhubDashboard;
  for (const platform of dashboard.platforms) {
    const card = element("article", "card");
    append(card,
      element("h3", "card-title", CREATORHUB_PLATFORM_NAMES[platform.id]),
      element("p", "card-sub", "账号环境与采集记录")
    );
    const stats = element("div", "platform-numbers");
    for (const [label, count] of [
      ["账号", platform.accounts],
      ["监控", platform.monitors],
      ["已下载", platform.downloaded],
      ["评论", platform.comments]
    ]) {
      const number = element("span");
      append(number, element("strong", "", String(count)),
        document.createTextNode(label));
      stats.append(number);
    }
    card.append(stats);
    platforms.append(card);
  }

  if (dashboard.accounts.length) {
    accounts.append(element("h3", "panel-header", "已登录账号"));
    for (const account of dashboard.accounts) {
      const item = element("div", "card");
      append(item,
        element("h3", "card-title", account.nickname),
        element("p", "card-sub",
          CREATORHUB_PLATFORM_NAMES[account.platform] + " · " +
          account.status + " · " +
          (account.creator_logged_in ? "创作中心已授权" : "创作中心待授权"))
      );
      accounts.append(item);
    }
  } else {
    accounts.append(element("p", "helper",
      "登录平台账号后，这里会显示账号状态。账号、监控规则、发布任务和互动管理可在 XHotLab 多平台运营中心操作。"));
  }

  const captions = {
    monitors: "作品监控",
    collections: "关键词采集",
    publish_tasks: "发布任务",
    downloads: "下载历史"
  };
  let shown = 0;
  for (const [key, label] of Object.entries(captions)) {
    const items = state.creatorhubActivity[key];
    if (!items?.length) continue;
    shown += items.length;
    const card = element("article", "card");
    append(card, element("h3", "card-title", label),
      element("p", "card-sub", "最近 " + items.length + " 条真实记录"));
    for (const item of items.slice(0, 4)) {
      const row = element("p", "card-text",
        (CREATORHUB_PLATFORM_NAMES[item.platform] || "多平台") + " · " +
        (item.title || ("任务 " + item.id)) + " · " +
        (item.status || (item.enabled ? "已启用" : "待处理")));
      card.append(row);
    }
    activity.append(card);
  }
  if (!shown) {
    activity.append(element("div", "placeholder",
      "当前没有采集、监控、下载或发布任务，创建后会显示在这里。"));
  }
}

async function captureCurrentCreatorHubLink() {
  const tabs = await chrome.tabs.query({active: true, currentWindow: true});
  const tab = tabs[0];
  if (!tab?.url?.startsWith("https://")) {
    throw new Error("请切换到抖音、小红书、快手、视频号或 TikTok 的作品页面");
  }
  const address = new URL(tab.url);
  const supported = [
    "douyin.com", "iesdouyin.com", "xiaohongshu.com",
    "xhslink.com", "kuaishou.com", "kwai.com",
    "weixin.qq.com", "tiktok.com"
  ];
  if (!supported.some((domain) =>
    address.hostname === domain || address.hostname.endsWith("." + domain))) {
    throw new Error("当前网页不属于 CreatorHub 支持的五个平台");
  }
  byId("creatorhub-share-link").value = tab.url;
  setNotice("已读取当前平台作品链接");
}

async function creatorhubShare(download) {
  const url = byId("creatorhub-share-link").value.trim();
  if (!url) throw new Error("请填写作品链接或使用「读取当前网页」");
  const selectedAccount = byId("creatorhub-share-account").value;
  setNotice(download ? "正在下载原帖素材…" : "正在解析作品信息…");
  const result = await request("/api/creatorhub/share", {
    method: "POST",
    body: JSON.stringify({
      url, download,
      account_id: selectedAccount ? Number(selectedAccount) : null
    })
  });
  const output = byId("creatorhub-share-result");
  output.replaceChildren();
  for (const item of result.results) {
    if (!item.ok) {
      append(output, element("p", "card-text",
        (item.input_platform || "平台") + "：" + item.error));
      continue;
    }
    append(output,
      element("p", "card-text",
        "平台：" + (item.input_platform || "未知") +
        " · " + (download ? "媒体下载完成" : "作品解析完成"))
    );
    if (download && item.output_dir) {
      append(output, element("p", "card-source",
        "本地素材目录：" + item.output_dir));
    }
    if (item.metadata?.title) {
      append(output, element("p", "card-text", String(item.metadata.title)));
    }
  }
  if (!result.ok) throw new Error("部分作品处理失败，请查看详细结果");
  setNotice(download ? "CreatorHub 已保存媒体与来源信息" : "CreatorHub 已解析作品");
}

async function refreshTrends() {
  const category = byId("topic-filter").value;
  const sort = byId("sort-filter").value;
  const params = new URLSearchParams({limit: "36", sort});
  if (category !== "all") params.set("category", category);
  const [posts, overview] = await Promise.all([
    request("/api/trends?" + params.toString()),
    request("/api/overview")
  ]);
  state.trends = posts;
  byId("last-checked").textContent = "上次采集 " + age(overview.last_checked) +
    " · 每 " + overview.scan_interval_minutes + " 分钟采集";
  byId("connection").textContent = overview.zen.key_configured ?
    "● Zen 已连接" : "● 本机在线";
  byId("connection").className = "connection ok";
  if (state.view === "trends") renderTrends();
}

function renderTrends() {
  const parent = byId("trend-list");
  parent.replaceChildren();
  if (!state.trends.length) {
    parent.append(element("div", "placeholder", "当前筛选条件下没有近期 X 中文帖子。"));
    return;
  }
  for (const post of state.trends) {
    const card = element("article", "card");
    append(card,
      element("p", "card-sub", post.source + " · " + age(post.published_at)),
      element("h3", "card-title", post.title),
      element("p", "card-text", post.summary.slice(0, 220))
    );
    if (post.preview_url) {
      showImages(card, [{url: post.preview_url, label: "X 原帖图片"}]);
    }
    const footer = element("div", "card-actions");
    append(footer,
      element("span", "tag", "♥ " + post.volume + " · 热度 " +
        Math.round(post.fresh_score)),
      actionButton("创作图文 ✦", async () => {
        state.chosenTrend = post;
        await switchView("studio");
      }, "primary"),
      externalLink("原帖 ↗", post.url)
    );
    card.append(footer);
    parent.append(card);
  }
}

async function activeXTab() {
  const tabs = await chrome.tabs.query({active: true, currentWindow: true});
  const tab = tabs[0];
  if (!tab || !/^https:\/\/(www\.)?x\.com\//.test(tab.url || "")) {
    throw new Error("请先在 Edge 打开 X 网站并切换到要操作的帖子");
  }
  await chrome.scripting.executeScript({
    target: {tabId: tab.id},
    files: ["content.js"]
  });
  return tab;
}

async function readCurrentPost() {
  const tab = await activeXTab();
  const result = await chrome.tabs.sendMessage(tab.id, {type: "XH_GET_CURRENT_POST"});
  if (!result?.ok) {
    throw new Error(result?.error || "当前 X 帖子读取失败");
  }
  state.currentPost = result.post;
  renderCurrent();
  return result.post;
}

async function capturePost(post) {
  const result = await request("/api/extension/capture", {
    method: "POST",
    body: JSON.stringify(post)
  });
  state.chosenTrend = result.trend;
  await chrome.storage.session.set({xhotlabActiveTrend: result.trend.id});
  await refreshStudio();
  setNotice("已保存 X 原帖和 " + result.media_count + " 个媒体信息");
  return result;
}

function renderCurrent() {
  const parent = byId("current-post");
  parent.replaceChildren();
  if (!state.currentPost) {
    parent.append(element("div", "placeholder",
      "在 X 上打开一条帖子，点击「读取当前 X 原帖」，或者使用原帖下方的快捷按钮。"));
    return;
  }
  const post = state.currentPost;
  const card = element("div", "card");
  append(card, element("p", "card-sub", age(post.published_at)),
    element("p", "card-text", post.text), externalLink("查看 X 原帖 ↗", post.url));
  showImages(card, post.media.map((value) => ({url: value.preview})), "mini-media detail-media");
  card.append(actionButton("保存并进入图文创作", async () => {
    await capturePost(post);
    await switchView("studio");
  }, "primary"));
  parent.append(card);
}

async function refreshStudio() {
  state.packs = await request("/api/creative/packs");
  if (state.view === "studio") renderStudio();
}

function renderPack(parent, pack) {
  const card = element("article", "card");
  append(card,
    element("p", "card-sub", "已生成 · " + pack.model + " · " + age(pack.created_at)),
    element("h3", "card-title", pack.headline),
    element("p", "card-text", pack.hook)
  );
  showImages(card, pack.images.map((url) => ({url})), "mini-media detail-media");
  const actions = element("div", "card-actions");
  append(actions, actionButton("查看发布附件", async () => {
    const queue = await request("/api/queue");
    const matched = queue.find((value) => value.pack_id === pack.id);
    if (!matched) throw new Error("此素材包没有对应的待发布任务");
    state.chosenQueueId = matched.id;
    await switchView("queue");
  }, "primary"), externalLink("原帖来源 ↗", pack.source_url));
  card.append(actions);
  parent.append(card);
}

function renderStudio() {
  const parent = byId("studio-content");
  parent.replaceChildren();
  if (state.chosenTrend) {
    const trend = state.chosenTrend;
    const card = element("article", "card");
    append(card,
      element("p", "card-sub", "已选择 · " + trend.source),
      element("h3", "card-title", trend.title),
      element("p", "card-text", trend.summary.slice(0, 260)),
      externalLink("打开原帖 ↗", trend.url)
    );
    const actions = element("div", "card-actions");
    actions.append(actionButton("✦ 用 Zen 生成完整图文", async () => {
      setNotice("Zen 正在写稿，ClickClick 正在生成三张原创配图…");
      const output = await request("/api/creative/run", {
        method: "POST",
        body: JSON.stringify({count: 1, trend_id: trend.id, refresh: false})
      });
      await refreshStudio();
      const pack = output.packs[0];
      const queue = await request("/api/queue");
      const match = queue.find((item) => item.pack_id === pack.id);
      if (!match) throw new Error("图文已生成，发布队列尚未登记");
      state.chosenQueueId = match.id;
      setNotice(output.reused ? "已读取现有完整图文" : "原创文案与三张配图已生成");
      await switchView("queue");
    }, "primary"));
    card.append(actions);
    parent.append(card);
  } else {
    parent.append(element("div", "placeholder",
      "在「热门」页面选择原帖，或从 X 当前页面一键采集。"));
  }

  const latest = state.chosenTrend
    ? state.packs.filter((pack) => pack.trend_id === state.chosenTrend.id)
    : state.packs.slice(0, 4);
  if (latest.length) {
    parent.append(element("h3", "panel-header", state.chosenTrend ?
      "当前原帖的图文素材" : "最近生成的素材"));
    for (const pack of latest) renderPack(parent, pack);
  }
}

async function refreshQueue() {
  state.queue = await request("/api/queue");
  if (state.view === "queue") renderQueue();
}

function activeQueueItem() {
  const preferred = state.queue.find((entry) => entry.id === state.chosenQueueId);
  const selected = preferred || state.queue.find((entry) =>
    entry.status === "queued" || entry.status === "opened") || state.queue[0];
  if (selected) state.chosenQueueId = selected.id;
  return selected;
}

function renderQueue() {
  const parent = byId("queue-content");
  parent.replaceChildren();
  const item = activeQueueItem();
  if (!item) {
    parent.append(element("div", "placeholder",
      "发布队列尚无内容。在「图文」页面生成完整图文后会自动加入这里。"));
    return;
  }
  const select = element("select", "input");
  select.setAttribute("aria-label", "选择待发布稿件");
  for (const entry of state.queue) {
    const option = element("option", "", entry.title.slice(0, 35));
    option.value = entry.id;
    option.selected = entry.id === item.id;
    select.append(option);
  }
  select.addEventListener("change", () => {
    state.chosenQueueId = select.value;
    renderQueue();
  });
  parent.append(select);

  const card = element("article", "card");
  const status = element("div", "row between");
  append(status, element("h3", "card-title", item.title),
    element("span", "status-chip", {
      queued: "等待发布", opened: "已打开", recorded: "已发布", skipped: "已跳过"
    }[item.status] || item.status));
  card.append(status);

  const editLabel = element("label", "label", "X 发帖文案");
  const editor = element("textarea", "input");
  editor.value = item.content;
  editor.id = "post-editor";
  editor.spellcheck = true;
  editor.disabled = item.status === "recorded";
  const chars = element("div", "editor-meta");
  chars.textContent = "当前 " + [...editor.value].length + " 个 Unicode 字符";
  editor.addEventListener("input", () => {
    chars.textContent = "当前 " + [...editor.value].length + " 个 Unicode 字符";
  });
  append(card, editLabel, editor, chars);

  const contentActions = element("div", "card-actions");
  contentActions.append(actionButton("保存文案", async () => {
    if (!editor.value.trim()) throw new Error("发帖文案不能为空");
    await request("/api/drafts/" + item.draft_id, {
      method: "PUT", body: JSON.stringify({content: editor.value.trim()})
    });
    await refreshQueue();
    setNotice("文案已保存到 XHotLab 草稿库");
  }));
  card.append(contentActions);

  if (item.video_source) {
    const source = item.video_source;
    append(card,
      element("p", "info-line",
        "抖音计划发布时间：" + new Date(source.scheduled_at)
          .toLocaleString("zh-CN", {timeZone: "Asia/Shanghai"}) +
        "（北京时间）"),
      element("p", "card-sub",
        "原作者：" + source.author_name)
    );
  }
  card.append(element("h3", "panel-header", "媒体附件 · 四张图片或一个视频"));
  const mediaGrid = element("div", "media-grid");
  for (const choice of item.attachments) {
    const tile = element("label", "media-tile" + (choice.selected ? " selected" : "") +
      (!choice.ready ? " unready" : ""));
    const img = element(choice.kind === "video" ? "video" : "img");
    img.src = imageUrl(choice.url);
    if (choice.kind === "video") {
      img.controls = true;
      img.preload = "metadata";
    } else {
      img.alt = choice.label;
      img.loading = "lazy";
    }
    const check = element("input");
    check.type = "checkbox";
    check.checked = choice.selected;
    check.disabled = !choice.ready || item.status === "recorded";
    check.addEventListener("change", () => perform(check, async () => {
      const choices = (choice.kind === "video" ? [] : item.attachments.filter(
        (candidate) => candidate.selected && candidate.kind !== "video" &&
          candidate.id !== choice.id
      ).map((candidate) => candidate.id));
      if (check.checked) choices.push(choice.id);
      if (choices.length > 4) throw new Error("每条 X 帖子最多四张图片");
      await request("/api/queue/" + item.id + "/media", {
        method: "PUT", body: JSON.stringify({media_ids: choices})
      });
      await refreshQueue();
      setNotice("已保存图片选择");
    }));
    append(tile, img, append(element("span"), check, choice.label.slice(0, 22)));
    mediaGrid.append(tile);
  }
  card.append(mediaGrid);

  const input = element("input");
  input.type = "file";
  input.accept = "image/png,image/jpeg,image/webp,image/gif";
  input.multiple = true;
  input.hidden = true;
  input.addEventListener("change", () => perform(null, async () => {
    await uploadLocalImages(item, input.files);
    input.value = "";
  }));
  card.append(input);
  const videoInput = element("input");
  videoInput.type = "file";
  videoInput.accept = "video/mp4,.mp4";
  videoInput.hidden = true;
  videoInput.addEventListener("change", () => perform(null, async () => {
    if (videoInput.files.length !== 1) return;
    const payload = new FormData();
    payload.append("file", videoInput.files[0]);
    setNotice("正在上传 MP4 并校验视频编码…");
    await request("/api/queue/" + item.id + "/video/upload", {
      method: "POST", body: payload
    });
    videoInput.value = "";
    await refreshQueue();
    setNotice("视频已校验并加入发布队列");
  }));
  card.append(videoInput);
  const mediaActions = element("div", "card-actions");
  append(mediaActions,
    actionButton("＋ 本地图片", async () => input.click()),
    actionButton("↓ 导入原帖图片", async () => {
      setNotice("正在从 X CDN 保存原帖媒体…");
      await request("/api/queue/" + item.id + "/media/import", {method: "POST"});
      await refreshQueue();
      setNotice("原帖图片已导入，点击图片即可选择");
    }),
    actionButton("选择原创图卡", async () => {
      const ids = item.attachments.filter((entry) =>
        entry.origin === "generated" && entry.ready).map((entry) => entry.id);
      if (!ids.length) throw new Error("这条内容尚未生成原创图卡");
      await request("/api/queue/" + item.id + "/media", {
        method: "PUT", body: JSON.stringify({media_ids: ids.slice(0, 4)})
      });
      await refreshQueue();
      setNotice("已经选择原创配图");
    })
  );
  mediaActions.append(actionButton("＋ 上传 MP4 视频", async () =>
    videoInput.click()));
  card.append(mediaActions);

  const drop = element("div", "source-note",
    "将本地图片拖进这里，或点击「＋ 本地图片」。X 原帖图片与 AI 配图均可自由组合。");
  drop.addEventListener("dragover", (event) => event.preventDefault());
  drop.addEventListener("drop", (event) => {
    event.preventDefault();
    perform(null, () => uploadLocalImages(item, event.dataTransfer.files));
  });
  card.append(drop);
  card.append(element("div", "divider"));

  const submit = actionButton("在当前 Edge 主窗口准备发布", async () => {
    const updated = await request("/api/queue");
    const latest = updated.find((entry) => entry.id === item.id);
    if (!latest) throw new Error("发布任务已不存在");
    if (editor.value.trim() !== latest.content) {
      await request("/api/drafts/" + item.draft_id, {
        method: "PUT", body: JSON.stringify({content: editor.value.trim()})
      });
      latest.content = editor.value.trim();
    }
    await fillXComposer(latest);
    setNotice("已经在当前 Edge 主窗口填入文案和媒体，请检查 X 编辑器后发布");
  }, "primary wide");
  submit.disabled = item.status === "recorded";
  card.append(submit);
  card.append(element("p", "helper",
    "直接使用当前 Edge 主窗口和已登录的 X 账号。插件会填入文案并上传选中的媒体，最后由你检查并确认发布。"));
  parent.append(card);
}

async function uploadLocalImages(queueItem, files) {
  if (!files?.length) return;
  const selected = queueItem.attachments.filter((value) => value.selected).length;
  if (selected + files.length > 4) {
    throw new Error("当前已选择 " + selected + " 张，请取消部分图片再导入");
  }
  const payload = new FormData();
  for (const file of files) payload.append("files", file);
  setNotice("正在导入 " + files.length + " 张本地图片…");
  await request("/api/queue/" + queueItem.id + "/media/upload", {
    method: "POST", body: payload
  });
  await refreshQueue();
  setNotice("本地图片已保存并加入待发布附件");
}

async function fillXComposer(queueItem) {
  setNotice("正在连接当前 Edge 主窗口的 X 标签页…");
  const result = await new Promise((resolve, reject) => {
    const port = chrome.runtime.connect({name: "XH_PREPARE_QUEUE_ITEM"});
    let finished = false;
    const timeout = setTimeout(() => {
      complete(new Error("视频上传任务超时，请检查 X 编辑器与网络状态"));
    }, 240000);
    const complete = (error, response) => {
      if (finished) return;
      finished = true;
      clearTimeout(timeout);
      port.disconnect();
      if (error) reject(error);
      else resolve(response);
    };
    port.onMessage.addListener((message) => {
      if (message?.type === "progress") {
        setNotice(message.text);
      } else if (message?.type === "result") {
        complete(message.ok ? null :
          new Error(message.error || "当前 Edge 编辑器准备失败"), message);
      }
    });
    port.onDisconnect.addListener(() => {
      if (finished) return;
      complete(new Error(chrome.runtime.lastError?.message ||
        "XHotLab 扩展后台连接中断，请在 edge://extensions 刷新扩展后重试"));
    });
    port.postMessage({queueId: queueItem.id});
  });
  setNotice(result.video ? "已在 X 编辑器添加视频，请等待平台处理完成并检查发布" :
    "已在 X 编辑器添加文案和图片，请检查后确认发布");
}

async function startup() {
  const version = chrome.runtime.getManifest().version;
  const background = await chrome.runtime.sendMessage({type: "XH_VERSION"});
  if (!background?.ok || background.version !== version || !background.supportsPort) {
    setNotice("正在刷新 XHotLab 的浏览器后台组件，请重新打开侧边栏…");
    chrome.runtime.reload();
    return;
  }
  const response = await request("/api/health");
  if (!response.ok) throw new Error("XHotLab 后台没有启动");
  await refreshTrends();
  await refreshStudio();
  await refreshQueue();
  const saved = await chrome.storage.session.get("xhotlabActiveTrend");
  if (saved.xhotlabActiveTrend) {
    state.chosenTrend = await request("/api/trends/" + saved.xhotlabActiveTrend);
  }
  renderCurrent();
  setNotice("XHotLab 已连接，可直接在浏览器中创作");
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () =>
    switchView(tab.dataset.view).catch((error) => setNotice(error.message, true)));
});
byId("refresh-trends").addEventListener("click", (event) =>
  perform(event.currentTarget, refreshTrends));
byId("refresh-studio").addEventListener("click", (event) =>
  perform(event.currentTarget, refreshStudio));
byId("refresh-queue").addEventListener("click", (event) =>
  perform(event.currentTarget, refreshQueue));
byId("topic-filter").addEventListener("change", () =>
  refreshTrends().catch((error) => setNotice(error.message, true)));
byId("sort-filter").addEventListener("change", () =>
  refreshTrends().catch((error) => setNotice(error.message, true)));
byId("capture-current").addEventListener("click", (event) =>
  perform(event.currentTarget, readCurrentPost));
byId("open-workspace").addEventListener("click", () =>
  chrome.tabs.create({url: API + "/?view=creatorhub", active: true}));
byId("refresh-channels").addEventListener("click", (event) =>
  perform(event.currentTarget, refreshChannels));
byId("douyin-sync").addEventListener("click", (event) =>
  perform(event.currentTarget, async () => {
    const value = await request("/api/douyin/sync", {
      method: "POST", body: JSON.stringify({})
    });
    await refreshChannels();
    setNotice("已从 CreatorHub 读取 " + value.discovered + " 条真实抖音视频");
  }));
byId("douyin-arrange").addEventListener("click", (event) =>
  perform(event.currentTarget, async () => {
    await chrome.tabs.create({url: API + "/", active: true});
  }));
byId("creatorhub-current-link").addEventListener("click", (event) =>
  perform(event.currentTarget, captureCurrentCreatorHubLink));
byId("creatorhub-inspect").addEventListener("click", (event) =>
  perform(event.currentTarget, () => creatorhubShare(false)));
byId("creatorhub-download").addEventListener("click", (event) =>
  perform(event.currentTarget, () => creatorhubShare(true)));

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type !== "XH_CAPTURED") return;
  (async () => {
    state.chosenTrend = await request("/api/trends/" + message.trendId);
    await switchView("studio");
    setNotice("已从 X 页面保存原帖，可直接生成图文");
  })().catch((error) => setNotice(error.message, true));
});

setInterval(() => {
  if (document.visibilityState !== "visible") return;
  if (state.view === "trends") {
    refreshTrends().catch((error) => setNotice(error.message, true));
  }
}, 3 * 60 * 1000);

startup().catch((error) => {
  byId("connection").className = "connection bad";
  byId("connection").textContent = "● 本机离线";
  setNotice(error.message + "，请先启动 XHotLab 后台服务", true);
});
