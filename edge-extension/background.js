const LOCAL_API = "http://127.0.0.1:8766";
const SCHEDULE_ALARM = "xhotlab-publish-window";
const VIDEO_CHUNK_BYTES = 256 * 1024;
const MAX_VIDEO_BYTES = 512 * 1024 * 1024;

async function apiGet(path) {
  const response = await fetch(LOCAL_API + path, {cache: "no-store"});
  const body = await response.json();
  if (!response.ok) {
    throw new Error(typeof body.detail === "string" ? body.detail :
      "读取 XHotLab 数据失败 HTTP " + response.status);
  }
  return body;
}

function isXTab(tab) {
  const address = tab?.pendingUrl || tab?.url;
  if (!address || !URL.canParse(address)) return false;
  const url = new URL(address);
  return url.protocol === "https:" &&
    (url.hostname === "x.com" || url.hostname === "www.x.com");
}

async function waitForTab(tabId) {
  const current = await chrome.tabs.get(tabId);
  if (current.status === "complete") return current;
  await new Promise((resolve, reject) => {
    let timer;
    const onUpdated = (changedId, info) => {
      if (changedId !== tabId || info.status !== "complete") return;
      clearTimeout(timer);
      chrome.tabs.onUpdated.removeListener(onUpdated);
      resolve();
    };
    chrome.tabs.onUpdated.addListener(onUpdated);
    timer = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(onUpdated);
      reject(new Error("当前 Edge 的 X 页面加载超时"));
    }, 30000);
    chrome.tabs.get(tabId).then((latest) => {
      if (latest.status === "complete") {
        clearTimeout(timer);
        chrome.tabs.onUpdated.removeListener(onUpdated);
        resolve();
      }
    }).catch((error) => {
      clearTimeout(timer);
      chrome.tabs.onUpdated.removeListener(onUpdated);
      reject(error);
    });
  });
  return chrome.tabs.get(tabId);
}

async function currentXTab() {
  const tabs = await chrome.tabs.query({currentWindow: true});
  const existing = tabs.find((entry) => entry.active && isXTab(entry)) ||
    tabs.find(isXTab);
  let tab;
  if (!existing) {
    tab = await chrome.tabs.create({url: "https://x.com/compose/post", active: true});
  } else {
    const current = existing.url || existing.pendingUrl;
    const isComposer = typeof current === "string" &&
      /^https:\/\/(?:www\.)?x\.com\/compose\/post(?:[/?#]|$)/.test(current);
    tab = await chrome.tabs.update(existing.id, isComposer
      ? {active: true}
      : {url: "https://x.com/compose/post", active: true});
  }
  tab = await waitForTab(tab.id);
  const finalAddress = tab.url || tab.pendingUrl;
  if (!finalAddress || !URL.canParse(finalAddress)) {
    throw new Error("X 编辑器尚未加载有效地址，请检查 Edge 网络连接并重新打开 X");
  }
  const url = new URL(finalAddress);
  if (url.pathname.startsWith("/i/flow/login") || url.pathname === "/login") {
    throw new Error("当前 Edge 主窗口尚未登录 X，请先在这个窗口完成登录");
  }
  if (url.hostname !== "x.com" && url.hostname !== "www.x.com") {
    throw new Error("X 编辑器跳转到了其他网站，请检查账号登录状态");
  }
  if (!/^\/compose\/post(?:\/|$)/.test(url.pathname)) {
    throw new Error("X 发帖窗口尚未打开，请确认账号登录后重新发起发布");
  }
  try {
    await chrome.scripting.executeScript({target: {tabId: tab.id}, files: ["content.js"]});
  } catch (error) {
    if (/error page/i.test(error.message)) {
      throw new Error("X 页面加载失败，请检查 Edge 的网络代理与 X 网站连接");
    }
    throw new Error("X 编辑器连接失败：" + error.message);
  }
  return tab;
}

function bytesToBase64(bytes) {
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
  }
  return btoa(binary);
}

function waitForPortReply(port, id, expectedType) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      port.onMessage.removeListener(onMessage);
      port.onDisconnect.removeListener(onDisconnect);
      reject(new Error("X 页面媒体传输响应超时"));
    }, 120000);
    const cleanup = () => {
      clearTimeout(timer);
      port.onMessage.removeListener(onMessage);
      port.onDisconnect.removeListener(onDisconnect);
    };
    const onMessage = (message) => {
      if (message?.id !== id) return;
      if (message.type === "error") {
        cleanup();
        reject(new Error(message.error || "X 页面处理视频失败"));
      } else if (message.type === expectedType) {
        cleanup();
        resolve(message);
      }
    };
    const onDisconnect = () => {
      const error = chrome.runtime.lastError;
      cleanup();
      reject(new Error(error?.message || "X 页面媒体连接已断开"));
    };
    port.onMessage.addListener(onMessage);
    port.onDisconnect.addListener(onDisconnect);
  });
}

async function sendPortMessage(port, message, expectedType) {
  const reply = waitForPortReply(port, message.id, expectedType);
  port.postMessage(message);
  return reply;
}

async function selectedImages(attachments) {
  const images = [];
  for (const attachment of attachments) {
    const url = new URL(attachment.url, LOCAL_API);
    if (url.origin !== LOCAL_API ||
        !/^\/(generated|source-media|user-media)\//.test(url.pathname)) {
      throw new Error("图片附件地址不属于本机 XHotLab 素材库");
    }
    const response = await fetch(url.href, {cache: "no-store"});
    if (!response.ok) throw new Error("读取图片附件失败 HTTP " + response.status);
    const blob = await response.blob();
    if (!blob.type.startsWith("image/") || blob.size > 12 * 1024 * 1024) {
      throw new Error("图片附件格式或大小不符合 X 上传要求");
    }
    const extension = {"image/png": "png", "image/jpeg": "jpg",
      "image/webp": "webp", "image/gif": "gif"}[blob.type];
    if (!extension) throw new Error("图片附件格式无法上传");
    images.push({
      name: "xhotlab-" + (images.length + 1) + "." + extension,
      mime: blob.type,
      data: "data:" + blob.type + ";base64," + bytesToBase64(new Uint8Array(await blob.arrayBuffer()))
    });
  }
  return images;
}

async function uploadVideoToComposer(tabId, queueItem, attachment) {
  const url = new URL(attachment.url, LOCAL_API);
  if (url.origin !== LOCAL_API || !/^\/(source-videos|user-media)\//.test(url.pathname)) {
    throw new Error("视频附件地址不属于本机 XHotLab 视频库");
  }
  const response = await fetch(url.href, {cache: "no-store"});
  if (!response.ok) throw new Error("读取 MP4 视频失败 HTTP " + response.status);
  const mime = response.headers.get("content-type")?.split(";")[0].trim();
  if (mime !== "video/mp4") throw new Error("视频附件服务器返回的格式不是 MP4");
  const expectedSize = Number(response.headers.get("content-length") || 0);
  if (expectedSize > MAX_VIDEO_BYTES) throw new Error("视频超过 512 MiB 上传限制");
  if (!response.body) throw new Error("浏览器无法读取视频数据流");

  const filename = String(
    queueItem.video_source?.video_file?.split(/[\\/]/).pop() || attachment.label || "xhotlab-video.mp4"
  ).replace(/[<>:"/\\|?*\u0000-\u001f]/g, "_").slice(0, 120);
  const port = chrome.tabs.connect(tabId, {name: "XH_UPLOAD_VIDEO"});
  try {
    await sendPortMessage(port, {
      type: "start", id: "start", filename, mime, expectedSize,
      text: queueItem.content
    }, "ack");
    const reader = response.body.getReader();
    let total = 0;
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > MAX_VIDEO_BYTES) throw new Error("视频超过 512 MiB 上传限制");
      for (let offset = 0; offset < value.length; offset += VIDEO_CHUNK_BYTES) {
        const chunk = value.subarray(offset, Math.min(offset + VIDEO_CHUNK_BYTES, value.length));
        await sendPortMessage(port, {
          type: "chunk", id: "chunk", data: bytesToBase64(chunk)
        }, "ack");
      }
    }
    if (expectedSize && total !== expectedSize) {
      throw new Error("视频传输长度与本机文件大小不一致");
    }
    const result = await sendPortMessage(port, {type: "end", id: "end", total}, "done");
    return {video: true, bytes: result.bytes, filename};
  } catch (error) {
    try { port.postMessage({type: "abort", id: "abort"}); } catch {}
    throw error;
  } finally {
    port.disconnect();
  }
}

async function prepareQueueItem(queueId, report = () => {}) {
  if (typeof queueId !== "string" || !queueId) {
    throw new Error("发布任务编号无效");
  }
  report("正在读取本机发布任务…");
  const queue = await apiGet("/api/queue");
  const item = queue.find((entry) => entry.id === queueId);
  if (!item) throw new Error("发布队列中找不到这条内容");
  if (item.status !== "queued" && item.status !== "opened") {
    throw new Error("这条内容当前状态不允许准备发布");
  }
  const selected = item.attachments.filter((entry) => entry.selected);
  if (selected.some((entry) => !entry.ready)) {
    throw new Error("请先准备好所有选中的媒体附件");
  }
  const videos = selected.filter((entry) => entry.kind === "video");
  if (videos.length && (videos.length !== 1 || selected.length !== 1)) {
    throw new Error("一条 X 帖子只能选择一个视频附件");
  }
  if (selected.length > 4) throw new Error("一条 X 帖子最多选择四张图片");

  report("正在打开当前 Edge 窗口中的 X 编辑器…");
  const tab = await currentXTab();
  if (videos.length) {
    report("正在把所选 MP4 传送到 X 编辑器…");
    const result = await uploadVideoToComposer(tab.id, item, videos[0]);
    return {ok: true, tabId: tab.id, ...result};
  }
  report("正在读取图片并填写 X 编辑器…");
  const images = await selectedImages(selected);
  const result = await chrome.tabs.sendMessage(tab.id, {
    type: "XH_PREPARE_COMPOSER",
    payload: {text: item.content, images}
  });
  if (!result?.ok) throw new Error(result?.error || "X 编辑器内容填入失败");
  return {ok: true, tabId: tab.id, images: result.images};
}

async function updatePublishBadge() {
  const response = await fetch(LOCAL_API + "/api/douyin/videos", {
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error("读取本机 X 发布计划失败 HTTP " + response.status);
  }
  const candidates = await response.json();
  const now = Date.now();
  const due = candidates.filter((item) =>
    item.queue_id &&
    (item.queue_status === "queued" || item.queue_status === "opened") &&
    item.scheduled_at &&
    Date.parse(item.scheduled_at) <= now
  );
  await chrome.action.setBadgeText({text: due.length ? String(due.length) : ""});
  await chrome.action.setBadgeBackgroundColor({color: "#7758D3"});
  await chrome.action.setTitle({title: due.length
    ? "XHotLab · " + due.length + " 条 X 内容已到发布窗口"
    : "打开 XHotLab 创作侧边栏"});
}

function registerPublishCheck() {
  chrome.alarms.create(SCHEDULE_ALARM, {periodInMinutes: 5});
  updatePublishBadge().catch(console.error);
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({openPanelOnActionClick: true});
  registerPublishCheck();
});
chrome.runtime.onStartup.addListener(registerPublishCheck);
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === SCHEDULE_ALARM) {
    updatePublishBadge().catch(console.error);
  }
});

function handlePublishPort(port) {
  if (port.name !== "XH_PREPARE_QUEUE_ITEM") return;
  let started = false;
  port.onMessage.addListener((message) => {
    if (started) return;
    started = true;
    const report = (text) => port.postMessage({type: "progress", text});
    prepareQueueItem(message?.queueId, report)
      .then((result) => port.postMessage({type: "result", ...result}))
      .catch((error) => port.postMessage({type: "result", ok: false, error: error.message}));
  });
}

function allowedLocalWebPage(sender) {
  if (!sender?.url || !URL.canParse(sender.url)) return false;
  const address = new URL(sender.url);
  return address.protocol === "http:" && address.hostname === "127.0.0.1" &&
    address.port === "8766";
}

chrome.runtime.onConnect.addListener(handlePublishPort);
chrome.runtime.onConnectExternal.addListener((port) => {
  if (!allowedLocalWebPage(port.sender)) {
    port.disconnect();
    return;
  }
  handlePublishPort(port);
});

chrome.runtime.onMessageExternal.addListener((message, sender, sendResponse) => {
  if (!allowedLocalWebPage(sender)) return;
  if (message?.type === "XH_STATUS") {
    sendResponse({ok: true, version: chrome.runtime.getManifest().version,
      connected: true});
  }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "XH_VERSION") {
    sendResponse({ok: true, version: chrome.runtime.getManifest().version, supportsPort: true});
    return;
  }
  if (message?.type === "XH_SCHEDULE_REFRESH") {
    updatePublishBadge().then(() => sendResponse({ok: true}))
      .catch((error) => sendResponse({ok: false, error: error.message}));
    return true;
  }
  if (message?.type === "XH_PREPARE_QUEUE_ITEM") {
    prepareQueueItem(message.queueId)
      .then((result) => sendResponse(result))
      .catch((error) => sendResponse({ok: false, error: error.message}));
    return true;
  }
  if (!message || message.type !== "XH_CAPTURE") return;
  if (!sender.tab || !/^https:\/\/(www\.)?x\.com\//.test(sender.tab.url || "")) {
    sendResponse({ok: false, error: "当前页面不属于 X"});
    return;
  }

  // 用户点击帖子按钮时，立即打开侧边栏，保证符合浏览器的用户手势要求。
  chrome.sidePanel.open({windowId: sender.tab.windowId}).catch(console.error);

  (async () => {
    const response = await fetch(LOCAL_API + "/api/extension/capture", {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-XHotLab-Action": "1"},
      body: JSON.stringify(message.post)
    });
    const body = await response.json();
    if (!response.ok) {
      throw new Error(typeof body.detail === "string" ? body.detail : "保存 X 帖子失败");
    }
    await chrome.storage.session.set({xhotlabActiveTrend: body.trend.id});
    chrome.runtime.sendMessage({
      type: "XH_CAPTURED",
      trendId: body.trend.id
    }).catch(() => {});
    sendResponse({ok: true, trendId: body.trend.id});
  })().catch((error) => sendResponse({ok: false, error: error.message}));
  return true;
});
