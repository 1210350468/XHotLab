const XHotLabPublish = (() => {
  const EXTENSION_VERSION = '1.2.9';
  const view = {
    videos: [], queue: [], selectedId: null, currentQueueId: null,
    running: false, initialized: false, editedCaptions: {},
  };
  const element = (id) => document.getElementById(id);

  function message(value) {
    element('publish-progress').textContent = value;
  }

  function guidance(title, detail, label, action) {
    element('publish-guidance-title').textContent = title;
    element('publish-guidance-detail').textContent = detail;
    const button = element('publish-guidance-action');
    button.textContent = label;
    button.onclick = action;
    element('publish-guidance').classList.remove('hidden');
  }

  function hideGuidance() {
    element('publish-guidance').classList.add('hidden');
  }

  function fixAction(error) {
    const detail = error.message || String(error);
    if (/请填写发布文案|文案超过/.test(detail)) {
      guidance('请填写完整的发布文案', detail, '返回文案输入框', () => element('publish-caption').focus());
    } else if (/账号|验证|风控|CreatorHub|采集/.test(detail)) {
      guidance('需要检查素材采集账号', detail, '打开平台账号管理', () => setView('creatorhub'));
    } else if (/登录 X|未登录/.test(detail)) {
      guidance('需要登录 X 账号', detail, '打开 X 登录页面', () => window.open('https://x.com/login', '_blank', 'noopener'));
    } else if (/X 页面加载失败|X 网站连接|网络代理|X 编辑器尚未加载有效地址/.test(detail)) {
      guidance('需要恢复 X 页面连接', detail,
        '在 Edge 打开 X', () => window.open('https://x.com/home', '_blank', 'noopener'));
    } else if (/扩展|extension|Extension|Receiving end|连接中断|chrome\.runtime|端口/.test(detail)) {
      guidance('需要启用 XHotLab Edge 插件',
        detail + '。打开 edge://extensions，刷新 XHotLab 插件 ' + EXTENSION_VERSION + '，然后回到这里继续。',
        '打开扩展设置说明', () => guidance('Edge 扩展目录',
          '在 edge://extensions 开启开发人员模式，选择项目根目录中的 edge-extension 文件夹。',
          '复制扩展设置地址', () => navigator.clipboard.writeText('edge://extensions')));
    } else {
      guidance('这一步需要处理', detail, '重新尝试', () => submit().catch((err) => fixAction(err)));
    }
  }

  function busy(value, text) {
    view.running = value;
    const selected = current();
    const queueItem = view.queue.find((item) => item.id === selected?.queue_id);
    const locked = queueItem?.status === 'recorded';
    for (const id of ['publish-refresh', 'publish-submit']) {
      element(id).disabled = value || (id !== 'publish-refresh' && (!view.selectedId || locked));
    }
    if (text) message(text);
  }

  function current() {
    return view.videos.find((entry) => entry.id === view.selectedId);
  }

  function fullCaption() {
    const text = element('publish-caption').value.trim();
    if (!text) throw new Error('请填写发布文案');
    if ([...text].length > 280) {
      throw new Error('发布文案超过 280 字，请精简正文');
    }
    return text;
  }

  function updateCount() {
    const text = element('publish-caption').value.trim();
    const count = [...text].length;
    element('publish-character-count').textContent = count + ' / 280';
    element('publish-character-count').classList.toggle('over-limit', count > 280);
  }

  function candidateMarkup(item) {
    const cover = item.cover_url && /^https:\/\//.test(item.cover_url)
      ? `<img loading="lazy" src="${escapeHtml(item.cover_url)}" alt="视频封面">`
      : '<span class="publish-candidate-cover"></span>';
    return `<button type="button" class="publish-candidate ${item.id === view.selectedId ? 'selected' : ''}"
        data-publish-id="${escapeHtml(item.id)}" role="option" aria-selected="${item.id === view.selectedId}">
        ${cover}<span class="publish-candidate-main"><span class="publish-candidate-title">${escapeHtml(item.description || '公开短视频')}</span>
        <span class="publish-candidate-author">${escapeHtml(item.author_name)}</span>
        <span class="publish-candidate-meta"><span>♥ ${Number(item.like_count).toLocaleString('zh-CN')} 赞</span>
        ${item.queue_id ? '<span>已加入发布安排</span>' : ''}</span></span></button>`;
  }

  function renderCandidates() {
    const target = element('publish-candidates');
    element('publish-more-sources').classList.toggle('hidden', view.videos.length > 0);
    if (!view.videos.length) {
      target.innerHTML = '<p class="publish-placeholder">当前还没有热门视频。点击「刷新素材」读取已有采集结果。</p>';
      return;
    }
    target.innerHTML = view.videos.map(candidateMarkup).join('');
  }

  function selectedMediaReady(item) {
    return item?.attachments?.some((attachment) =>
      attachment.kind === 'video' && attachment.selected && attachment.ready);
  }

  function select(candidateId) {
    const candidate = view.videos.find((item) => item.id === candidateId);
    if (!candidate) throw new Error('选中的视频已经失效，请刷新素材');
    if (view.selectedId && !element('publish-caption').disabled) {
      view.editedCaptions[view.selectedId] = element('publish-caption').value;
    }
    view.selectedId = candidate.id;
    view.currentQueueId = candidate.queue_id || null;
    renderCandidates();
    hideGuidance();
    const queueItem = view.queue.find((item) => item.id === candidate.queue_id);
    const poster = candidate.cover_url && /^https:\/\//.test(candidate.cover_url)
      ? `<img src="${escapeHtml(candidate.cover_url)}" alt="视频封面">` : '';
    element('publish-selected').innerHTML = `${poster}<div class="publish-selected-copy">
      <h3>${escapeHtml(candidate.description || '公开短视频')}</h3>
      <p>原作者：${escapeHtml(candidate.author_name)} · ${Number(candidate.like_count).toLocaleString('zh-CN')} 赞</p>
      <a target="_blank" rel="noopener noreferrer" href="${escapeHtml(candidate.source_url)}">查看原视频和作者</a></div>`;
    element('publish-caption').disabled = queueItem?.status === 'recorded';
    element('publish-caption').value = Object.hasOwn(view.editedCaptions, candidate.id)
      ? view.editedCaptions[candidate.id]
      : queueItem?.status === 'recorded' ? queueItem.content : '';
    element('publish-attribution').textContent = '仅发布你填写的正文';
    element('publish-media-state').textContent = queueItem?.status === 'recorded' ? '已经发布' :
      selectedMediaReady(queueItem) ? '视频已准备' : '待准备视频';
    element('publish-media-state').classList.toggle('ready', selectedMediaReady(queueItem));
    element('publish-after').classList.toggle('hidden', queueItem?.status !== 'opened');
    element('publish-submit').disabled = view.running || queueItem?.status === 'recorded';
    message(queueItem?.status === 'recorded' ? '这条视频已有发布记录。' :
      selectedMediaReady(queueItem) ? '视频已准备，可编辑文案并发送到 X。' :
      '文案完成后，系统会自动下载视频并打开 X 编辑器。');
    updateCount();
  }

  async function refresh(loadRemote = false) {
    busy(true, loadRemote ? '正在从采集服务读取最新作品…' : '正在读取已有热门视频…');
    try {
      if (loadRemote) {
        const status = await api('/api/creatorhub/status');
        if (!status.installed) throw new Error('素材采集服务尚未安装');
        if (!status.running) {
          await api('/api/creatorhub/start', {method: 'POST'});
        }
        await api('/api/douyin/sync', {method: 'POST', body: JSON.stringify({})});
      }
      const [videos, queue] = await Promise.all([api('/api/douyin/videos'), api('/api/queue')]);
      view.videos = videos.slice().sort((a, b) => b.like_count - a.like_count);
      view.queue = queue;
      renderCandidates();
      if (view.selectedId && view.videos.some((item) => item.id === view.selectedId)) {
        select(view.selectedId);
      } else if (view.videos.length) {
        const candidate = view.videos.find((item) => item.queue_status !== 'recorded') || view.videos[0];
        select(candidate.id);
      } else {
        guidance('还没有可发布的热门视频', '打开多平台运营中心配置采集关键词后，再点击刷新素材。',
          '打开采集中心', () => setView('creatorhub'));
      }
      if (loadRemote) message('已更新热门视频列表。');
    } catch (error) {
      fixAction(error, 'source');
      message('读取素材失败：' + error.message);
    } finally {
      busy(false);
    }
  }

  function prepareInExtension(queueId, extensionId) {
    return new Promise((resolve, reject) => {
      if (!globalThis.chrome?.runtime?.connect) {
        reject(new Error('Edge 扩展未连接：请在 edge://extensions 启用 XHotLab 插件 ' + EXTENSION_VERSION));
        return;
      }
      const port = chrome.runtime.connect(extensionId, {name: 'XH_PREPARE_QUEUE_ITEM'});
      let finished = false;
      const stop = (error, response) => {
        if (finished) return;
        finished = true;
        clearTimeout(timeout);
        port.disconnect();
        if (error) reject(error);
        else resolve(response);
      };
      const timeout = setTimeout(() => stop(new Error('视频上传等待超时，请检查 X 编辑器')), 240000);
      port.onMessage.addListener((payload) => {
        if (payload?.type === 'progress') message(payload.text);
        if (payload?.type === 'result') {
          stop(payload.ok ? null : new Error(payload.error || 'X 上传操作未完成'), payload);
        }
      });
      port.onDisconnect.addListener(() => {
        if (!finished) stop(new Error(chrome.runtime.lastError?.message || 'Edge 扩展连接中断'));
      });
      port.postMessage({queueId});
    });
  }

  function discoverExtensionId() {
    return new Promise((resolve, reject) => {
      const requestId = crypto.randomUUID();
      const onMessage = (event) => {
        if (event.origin !== location.origin || event.source !== window) return;
        if (event.data?.type !== 'XH_EXTENSION_FOUND' || event.data.requestId !== requestId) return;
        if (event.data.version !== EXTENSION_VERSION) return;
        clearTimeout(timeout);
        window.removeEventListener('message', onMessage);
        resolve(event.data.extensionId);
      };
      const timeout = setTimeout(() => {
        window.removeEventListener('message', onMessage);
        reject(new Error('没有检测到 XHotLab 插件 ' + EXTENSION_VERSION + '，请在 Edge 扩展设置中刷新插件'));
      }, 2000);
      window.addEventListener('message', onMessage);
      window.postMessage({type: 'XH_DISCOVER_EXTENSION', requestId}, location.origin);
    });
  }

  async function checkExtension() {
    if (!globalThis.chrome?.runtime?.sendMessage) {
      throw new Error('Edge 扩展未连接，请在 edge://extensions 启用 XHotLab 插件');
    }
    const extensionId = await discoverExtensionId();
    const response = await new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(extensionId, {type: 'XH_STATUS'}, (result) => {
        const error = chrome.runtime.lastError;
        if (error) reject(new Error('XHotLab Edge 扩展连接失败：' + error.message));
        else resolve(result);
      });
    });
    if (!response?.ok || response.version !== EXTENSION_VERSION) {
      throw new Error('Edge 扩展版本需要更新到 ' + EXTENSION_VERSION + '，请刷新 XHotLab 扩展');
    }
    return extensionId;
  }

  async function submit() {
    const candidate = current();
    if (!candidate || view.running) return;
    let caption;
    try {
      caption = fullCaption();
    } catch (error) {
      fixAction(error);
      message(error.message);
      return;
    }
    busy(true, '正在准备发布任务…');
    hideGuidance();
    try {
      const extensionId = await checkExtension();
      let queueId = candidate.queue_id;
      if (!queueId) {
        const arranged = await api('/api/douyin/arrange', {
          method: 'POST', body: JSON.stringify({count: 1, candidate_id: candidate.id,
            captions: {[candidate.id]: caption}}),
        });
        if (arranged.arranged !== 1) throw new Error('视频未能加入发布队列');
        queueId = arranged.posts[0].queue_id;
      } else {
        const existing = view.queue.find((item) => item.id === queueId);
        if (!existing) throw new Error('已安排的视频发布任务未找到，请刷新素材');
        if (existing.status === 'recorded') throw new Error('这条视频已有发布记录');
        if (existing.content !== caption) {
          await api('/api/drafts/' + encodeURIComponent(existing.draft_id), {
            method: 'PUT', body: JSON.stringify({content: caption}),
          });
        } else if (existing.status === 'skipped') {
          await api('/api/queue/' + encodeURIComponent(queueId) + '/requeue', {method: 'POST'});
        }
      }
      view.currentQueueId = queueId;
      let items = await api('/api/queue');
      let queued = items.find((item) => item.id === queueId);
      if (!selectedMediaReady(queued)) {
        message('正在下载 MP4 并检查视频格式…');
        await api('/api/douyin/videos/' + encodeURIComponent(candidate.id) + '/download',
          {method: 'POST'});
        items = await api('/api/queue');
        queued = items.find((item) => item.id === queueId);
        if (!selectedMediaReady(queued)) throw new Error('视频上传附件尚未准备完成');
      }
      message('视频已就绪，正在连接 Edge 主窗口…');
      await prepareInExtension(queueId, extensionId);
      await api('/api/queue/' + encodeURIComponent(queueId) + '/open', {method: 'POST'});
      message('视频和文案已送入 X 编辑器，请在 X 页面确认发布。');
      view.editedCaptions[candidate.id] = element('publish-caption').value;
      await refresh();
      message('已打开 X 编辑器。请检查上传状态和账号，再点击「发布」。');
    } catch (error) {
      fixAction(error);
      message('发布准备未完成：' + error.message);
    } finally {
      busy(false);
    }
  }

  async function open() {
    if (!view.initialized) {
      view.initialized = true;
      element('publish-candidates').addEventListener('click', (event) => {
        const button = event.target.closest('[data-publish-id]');
        if (button && !view.running) select(button.dataset.publishId);
      });
      element('publish-caption').addEventListener('input', () => {
        if (view.selectedId) view.editedCaptions[view.selectedId] = element('publish-caption').value;
        updateCount();
      });
      element('publish-refresh').addEventListener('click', () => refresh(true));
      element('publish-submit').addEventListener('click', submit);
      element('publish-more-sources').addEventListener('click', () => setView('creatorhub'));
      element('publish-record').addEventListener('click', async () => {
        if (!view.currentQueueId) return;
        const url = element('publish-post-url').value.trim();
        if (!/^https:\/\/(?:www\.)?(?:x\.com|twitter\.com)\/[^/]+\/status\/\d+/.test(url)) {
          guidance('请填写实际发布的帖子链接', '打开已经发布的 X 帖子，复制地址栏中的链接。',
            '打开 X', () => window.open('https://x.com/home', '_blank', 'noopener'));
          return;
        }
        busy(true, '正在保存实际帖子链接…');
        try {
          await api('/api/queue/' + encodeURIComponent(view.currentQueueId) + '/record', {
            method: 'POST', body: JSON.stringify({post_url: url}),
          });
          delete view.editedCaptions[view.selectedId];
          await refresh();
          message('已登记这条 X 帖子的发布地址。');
        } catch (error) {
          fixAction(error);
          message(error.message);
        } finally {
          busy(false);
        }
      });
    }
    if (!view.videos.length) await refresh();
  }

  return {open};
})();
