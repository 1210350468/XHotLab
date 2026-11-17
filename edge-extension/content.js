(() => {
  const CONTENT_VERSION = "1.2.9";
  if (globalThis.__XHOTLAB_CONTENT_VERSION__ === CONTENT_VERSION) return;
  globalThis.__XHOTLAB_CONTENT_VERSION__ = CONTENT_VERSION;
  globalThis.__XHOTLAB_CONTENT_ACTIVE__ = true;

  const POST_PATH = /^\/([A-Za-z0-9_]{1,15})\/status\/(\d{10,20})(?:\/|$)/;

  function findOriginalUrl(article) {
    const time = article.querySelector("time");
    const primary = time && time.closest('a[href*="/status/"]');
    const anchor = primary || article.querySelector('a[href*="/status/"]');
    if (!anchor) return null;
    const parsed = new URL(anchor.href, "https://x.com");
    const matched = parsed.pathname.match(POST_PATH);
    if (!matched) return null;
    return "https://x.com/" + matched[1] + "/status/" + matched[2];
  }

  function readEngagement(article) {
    const element = article.querySelector('[data-testid="like"]');
    const candidate = element && (element.getAttribute("aria-label") || element.textContent || "");
    if (!candidate) return 0;
    const match = candidate.replaceAll(",", "").match(/(\d+(?:\.\d+)?)(\s*[万千KkMm])?/);
    if (!match) return 0;
    const factor = {"万": 10000, "千": 1000, "K": 1000, "k": 1000,
      "M": 1000000, "m": 1000000};
    return Math.round(Number(match[1]) * (factor[match[2]?.trim()] || 1));
  }

  function extractPost(article) {
    const url = findOriginalUrl(article);
    const tweetText = article.querySelector('[data-testid="tweetText"]');
    const text = tweetText && tweetText.innerText.trim();
    if (!url || !text || text.length < 12) {
      throw new Error("请打开包含正文的 X 原帖");
    }
    const timestamp = article.querySelector("time")?.getAttribute("datetime") || null;
    const urls = new Set();
    const media = [];
    for (const image of article.querySelectorAll('img[src*="pbs.twimg.com/"]')) {
      const src = image.currentSrc || image.src;
      const parsed = new URL(src);
      if (parsed.hostname !== "pbs.twimg.com") continue;
      if (!parsed.pathname.startsWith("/media/") &&
          !parsed.pathname.includes("_thumb/")) continue;
      if (urls.has(src)) continue;
      urls.add(src);
      media.push({
        url: src,
        preview: src,
        kind: parsed.pathname.startsWith("/media/") ? "photo" : "video",
        width: image.naturalWidth || 0,
        height: image.naturalHeight || 0
      });
    }
    return {
      url, text, published_at: timestamp,
      likes: readEngagement(article),
      media: media.slice(0, 12)
    };
  }

  function articleForPage() {
    const match = location.pathname.match(POST_PATH);
    if (!match) {
      throw new Error("请打开具体的 X 帖子，或点击时间线里的「✦ XHotLab」");
    }
    const target = "https://x.com/" + match[1] + "/status/" + match[2];
    for (const article of document.querySelectorAll('article[data-testid="tweet"]')) {
      if (findOriginalUrl(article) === target) return article;
    }
    throw new Error("X 页面尚未显示该帖子，等待正文加载后再试");
  }

  function addInlineButtons() {
    for (const article of document.querySelectorAll('article[data-testid="tweet"]')) {
      if (article.dataset.xhotlabReady === "1") continue;
      const actions = article.querySelector('[role="group"]');
      if (!actions || !findOriginalUrl(article)) continue;
      article.dataset.xhotlabReady = "1";
      const button = document.createElement("button");
      button.type = "button";
      button.className = "xhotlab-inline-action";
      button.textContent = "✦ XHotLab";
      button.title = "将此帖子和图片导入 XHotLab 创作工作台";
      button.addEventListener("click", async (event) => {
        event.preventDefault();
        event.stopPropagation();
        button.disabled = true;
        button.textContent = "正在采集…";
        try {
          const result = await chrome.runtime.sendMessage({
            type: "XH_CAPTURE", post: extractPost(article)
          });
          if (!result?.ok) throw new Error(result?.error || "采集失败");
          button.textContent = "✓ 已采集";
        } catch (error) {
          button.textContent = "重新采集";
          button.title = error.message;
        } finally {
          button.disabled = false;
        }
      });
      actions.append(button);
    }
  }

  function waitForEditor(timeoutMs) {
    return new Promise((resolve, reject) => {
      const find = () => document.querySelector(
        '[data-testid="tweetTextarea_0"] [contenteditable="true"],' +
        '[data-testid="tweetTextarea_0"][contenteditable="true"]'
      );
      const current = find();
      if (current) return resolve(current);
      const observer = new MutationObserver(() => {
        const next = find();
        if (!next) return;
        clearTimeout(timeout);
        observer.disconnect();
        resolve(next);
      });
      observer.observe(document.documentElement, {subtree: true, childList: true});
      const timeout = setTimeout(() => {
        observer.disconnect();
        reject(new Error("找不到 X 编辑器，请确认当前账号已登录"));
      }, timeoutMs);
    });
  }

  function decodeImage(file) {
    const separator = file.data.indexOf(",");
    if (!file.data.startsWith("data:image/") || separator < 0) {
      throw new Error("图片文件编码无效");
    }
    const binary = atob(file.data.slice(separator + 1));
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index++) {
      bytes[index] = binary.charCodeAt(index);
    }
    return new File([bytes], file.name, {type: file.mime});
  }

  function decodeBase64(value) {
    const binary = atob(value);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index++) {
      bytes[index] = binary.charCodeAt(index);
    }
    return bytes;
  }

  function waitForAttachment(timeoutMs) {
    return new Promise((resolve, reject) => {
      const find = () => {
        const container = document.querySelector('[data-testid="attachments"]');
        return container && (container.childElementCount > 0 ||
          container.querySelector("img, video, [data-testid='videoPlayer']"));
      };
      if (find()) return resolve();
      const observer = new MutationObserver(() => {
        if (!find()) return;
        clearTimeout(timeout);
        observer.disconnect();
        resolve();
      });
      observer.observe(document.documentElement, {subtree: true, childList: true, attributes: true});
      const timeout = setTimeout(() => {
        observer.disconnect();
        reject(new Error("X 编辑器尚未显示媒体附件，请检查当前页面的上传状态"));
      }, timeoutMs);
    });
  }

  async function prepareComposer(payload) {
    if (!payload || typeof payload.text !== "string" ||
        !Array.isArray(payload.images) || payload.images.length > 4 ||
        (payload.videoFile && !(payload.videoFile instanceof File)) ||
        (payload.videoFile && payload.images.length)) {
      throw new Error("待发布内容格式无效");
    }
    const editor = await waitForEditor(30000);
    editor.focus();
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(editor);
    selection.removeAllRanges();
    selection.addRange(range);
    if (!document.execCommand("insertText", false, payload.text)) {
      throw new Error("X 编辑器拒绝填入文案");
    }
    if (editor.innerText.trim() !== payload.text.trim()) {
      throw new Error("X 编辑器中的文案与草稿不一致，请在页面上检查");
    }

    if (payload.images.length > 0 || payload.videoFile) {
      const uploader = document.querySelector('input[data-testid="fileInput"]');
      if (!uploader || uploader.type !== "file") {
        throw new Error("找不到 X 图片或视频上传入口，请检查 X 页面");
      }
      const transfer = new DataTransfer();
      if (payload.videoFile) {
        if (payload.videoFile.type !== "video/mp4" || !payload.videoFile.name.toLowerCase().endsWith(".mp4")) {
          throw new Error("X 视频附件需要使用 MP4 格式");
        }
        transfer.items.add(payload.videoFile);
      } else {
        for (const item of payload.images) transfer.items.add(decodeImage(item));
      }
      uploader.files = transfer.files;
      uploader.dispatchEvent(new Event("input", {bubbles: true}));
      uploader.dispatchEvent(new Event("change", {bubbles: true}));
      await waitForAttachment(payload.videoFile ? 90000 : 30000);
    }
    return {
      text: true,
      images: payload.images.length,
      video: payload.videoFile ? {
        name: payload.videoFile.name,
        size: payload.videoFile.size
      } : null
    };
  }

  chrome.runtime.onConnect.addListener((port) => {
    if (port.name !== "XH_UPLOAD_VIDEO") return;
    let upload = null;
    port.onMessage.addListener((message) => {
      const messageId = message?.id || upload?.lastId || "upload";
      try {
        if (message?.type === "abort") {
          upload = null;
          return;
        }
        if (message?.type === "start") {
          if (upload) throw new Error("已有视频正在传输");
          if (typeof message.text !== "string" || !message.filename ||
              message.mime !== "video/mp4") {
            throw new Error("视频上传任务信息无效");
          }
          upload = {
            text: message.text,
            filename: message.filename,
            mime: message.mime,
            expectedSize: Number(message.expectedSize || 0),
            total: 0,
            chunks: [],
            lastId: messageId
          };
          port.postMessage({type: "ack", id: messageId});
          return;
        }
        if (!upload) throw new Error("视频传输尚未初始化");
        upload.lastId = messageId;
        if (message?.type === "chunk") {
          const bytes = decodeBase64(message.data);
          upload.total += bytes.byteLength;
          if (upload.total > 512 * 1024 * 1024) {
            throw new Error("视频超过 512 MiB 上传限制");
          }
          upload.chunks.push(bytes);
          port.postMessage({type: "ack", id: messageId});
          return;
        }
        if (message?.type === "end") {
          if (upload.total !== Number(message.total) ||
              (upload.expectedSize && upload.total !== upload.expectedSize)) {
            throw new Error("视频传输长度校验失败");
          }
          const file = new File(upload.chunks, upload.filename, {type: upload.mime});
          const text = upload.text;
          const size = upload.total;
          upload = null;
          prepareComposer({text, images: [], videoFile: file})
            .then(() => port.postMessage({type: "done", id: messageId, bytes: size}))
            .catch((error) => port.postMessage({type: "error", id: messageId, error: error.message}));
          return;
        }
        throw new Error("收到未知的视频传输消息");
      } catch (error) {
        upload = null;
        port.postMessage({type: "error", id: messageId, error: error.message});
      }
    });
  });

  chrome.runtime.onMessage.addListener((message, sender, respond) => {
    if (message?.type === "XH_GET_CURRENT_POST") {
      try {
        respond({ok: true, post: extractPost(articleForPage())});
      } catch (error) {
        respond({ok: false, error: error.message});
      }
      return;
    }
    if (message?.type === "XH_PREPARE_COMPOSER") {
      prepareComposer(message.payload)
        .then((value) => respond({ok: true, ...value}))
        .catch((error) => respond({ok: false, error: error.message}));
      return true;
    }
  });

  let pending = false;
  const observer = new MutationObserver(() => {
    if (pending) return;
    pending = true;
    setTimeout(() => {
      pending = false;
      addInlineButtons();
    }, 600);
  });
  observer.observe(document.body, {subtree: true, childList: true});
  addInlineButtons();
})();
