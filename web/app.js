const state = {
  category: 'all', view: 'trends', sort: 'hot', query: '',
  items: [], offset: 0, pageSize: 36, selected: null, draft: null,
  trendRequestSequence: 0,
};

const $ = (selector) => document.querySelector(selector);
const escapeHtml = (input) => String(input ?? '').replace(/[&<>"']/g, (c) =>
  ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const categoryNames = {
  all: 'X 中文热门', x_zh_general: '热门讨论',
  x_zh_ai: 'AI 与科技', x_zh_games: '游戏与影视',
  x_zh_life: '生活与趣事', x_zh_digital: '数码与互联网',
};

function relativeTime(text) {
  const delta = Math.max(0, Date.now() - new Date(text).getTime());
  const minutes = Math.floor(delta / 60000);
  if (!Number.isFinite(minutes)) return '时间未知';
  if (minutes < 60) return `${minutes} 分钟前`;
  if (minutes < 1440) return `${Math.floor(minutes / 60)} 小时前`;
  return `${Math.floor(minutes / 1440)} 天前`;
}

function safeUrl(raw) {
  const parsed = new URL(raw);
  if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') throw new Error('来源链接的协议无效');
  return parsed.href;
}

function safeMediaUrl(raw) {
  const parsed = new URL(raw, window.location.origin);
  if (parsed.origin === window.location.origin) {
    if (!/^\/(generated|source-media|source-videos|user-media)\//.test(parsed.pathname)) {
      throw new Error('媒体地址不属于本机素材库');
    }
  } else if (parsed.protocol !== 'https:' || parsed.hostname !== 'pbs.twimg.com') {
    throw new Error('原帖媒体地址来源无效');
  }
  return parsed.href;
}

async function api(path, init = {}) {
  const response = await fetch(path, {
    ...init,
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json',
      ...(init.method && init.method !== 'GET' ? {'X-XHotLab-Action': '1'} : {}),
      ...init.headers },
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : '请求失败，请检查服务状态');
  return payload;
}

function toast(message, error = false) {
  const element = document.createElement('div');
  element.className = 'toast' + (error ? ' error' : '');
  element.textContent = message;
  $('#toast-container').appendChild(element);
  setTimeout(() => element.remove(), 4300);
}

async function overview() {
  const data = await api('/api/overview');
  $('#stat-trends').textContent = data.total.toLocaleString();
  $('#stat-trending').textContent = (data.categories.find((c) => c.category === 'x_zh_general')?.count || 0).toLocaleString();
  $('#stat-sources').textContent = data.sources.filter((s) => s.status === 'ok').length + ' / ' + data.sources.length;
  $('#stat-drafts').textContent = data.drafts;
  $('#nav-all-count').textContent = data.total;
  $('#draft-count').textContent = data.drafts;
  await refreshQueueCount();
  $('#updated-tag').textContent = data.last_checked ? '● 最近采集 ' + relativeTime(data.last_checked) : '● 等待更新';
  $('#scan-time').textContent = data.last_checked
    ? '上次扫描：' + relativeTime(data.last_checked) + ' · 每 ' + data.scan_interval_minutes + ' 分钟自动采集'
    : '等待首次扫描';
  return data;
}

async function refreshQueueCount() {
  const items = await api('/api/queue');
  $('#queue-count').textContent = items.filter((item) => item.status === 'queued' || item.status === 'opened').length;
}

function renderTrends() {
  const cards = $('#cards');
  if (!state.items.length) {
    cards.innerHTML = '<div class="empty-state"><div class="empty-icon">◌</div><h3>当前分类没有 X 中文帖子</h3><p>点击「搜索 X 中文热门」，或调整搜索词。</p></div>';
    $('#load-more').classList.add('hidden');
    return;
  }
  cards.innerHTML = state.items.map((item) => {
    const category = categoryNames[item.category] || item.category;
    const link = safeUrl(item.url);
    const traffic = item.volume ? `<span class="traffic">♥ ${Number(item.volume).toLocaleString()} 点赞</span>` : '';
    const thumbnail = item.preview_url
      ? `<div class="trend-media-preview"><img loading="lazy" src="${escapeHtml(safeMediaUrl(item.preview_url))}" alt="X 原帖媒体预览"><span>${item.media_count} 个媒体文件 · 来源 X 原帖</span></div>`
      : '';
    return `<article class="trend-card">
      <div class="card-content">
        <div class="card-topline"><span class="category-chip">${escapeHtml(category)}</span><span class="relative-time">${relativeTime(item.published_at)}</span><span class="source-label">${escapeHtml(item.source)}</span></div>
        <h3>${escapeHtml(item.title)}</h3>
        <p class="description">${escapeHtml(item.summary || '打开 X 原帖了解完整讨论内容。')}</p>
        ${thumbnail}
        <div class="card-meta"><span>◷ ${relativeTime(item.published_at)}</span>${traffic}<a class="source-link" href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">查看 X 原帖 ↗</a></div>
      </div>
        <div class="card-actions"><div class="priority"><span>实时热度</span><strong>${Math.round(item.fresh_score)}</strong></div>
        <div class="priority-bar"><i style="width:${item.fresh_score}%"></i></div>
        <button class="compose-button" data-action="compose" data-id="${item.id}">✦ AI 改编</button></div>
    </article>`;
  }).join('');
}

async function loadTrends(append = false) {
  if (state.view !== 'trends') return;
  const requestSequence = ++state.trendRequestSequence;
  if (!append) { state.offset = 0; state.items = []; }
  const params = new URLSearchParams({
    category: state.category, search: state.query, sort: state.sort,
    offset: state.offset, limit: state.pageSize,
  });
  const page = await api('/api/trends?' + params.toString());
  if (state.view !== 'trends' || requestSequence !== state.trendRequestSequence) return;
  state.items = append ? [...state.items, ...page] : page;
  state.offset = state.items.length;
  renderTrends();
  $('#load-more').classList.toggle('hidden', page.length < state.pageSize);
}

function setView(view, category = 'all') {
  if (view === 'creatorhub') {
    openCreatorHubWorkspace().catch((error) => toast(error.message, true));
    return;
  }
  state.trendRequestSequence += 1;
  state.view = view;
  state.category = category;
  const isPublish = view === 'publish';
  $('#publish-workspace').classList.toggle('hidden', !isPublish);
  for (const id of ['discovery-hero', 'discovery-stats', 'discovery-section', 'discovery-footer']) {
    $('#' + id).classList.toggle('hidden', isPublish);
  }
  $('#publish-nav').classList.toggle('active', isPublish);
  if (isPublish) {
    $('#breadcrumb-name').textContent = '发布到 X';
    document.querySelectorAll('.advanced-menu .nav-btn').forEach((node) => node.classList.remove('active'));
    XHotLabPublish.open().catch((error) => toast(error.message, true));
    return;
  }
  const isDrafts = view === 'drafts';
  const isPosts = view === 'queue';
  const isWorkspace = ['chat', 'profile', 'agent', 'creative'].includes(view);
  const workspaceNames = {chat:'AI 聊天工作台', profile:'创作者背景', agent:'Agent 操作任务',
    creative:'中文热点图文工厂'};
  $('#trends-toolbar').classList.toggle('hidden', isDrafts || isPosts || isWorkspace);
  $('#load-more').classList.toggle('hidden', isDrafts || isPosts || isWorkspace);
  $('#section-title').innerHTML = isWorkspace ? escapeHtml(workspaceNames[view]) + ' <span class="title-dot">✦</span>' :
    isPosts ? '待发布队列 <span class="title-dot">↗</span>' :
    isDrafts ? '创作草稿 <span class="title-dot">✎</span>' : escapeHtml(categoryNames[category]) + ' <span class="title-dot">✦</span>';
  $('#section-subtitle').textContent = isWorkspace ?
    ({chat:'多模型交流，利用个人背景与真实热点辅助内容决策',profile:'管理用于内容创作和 Agent 决策的背景信息',agent:'通过本机 Codex／Claude Code 执行需要授权的任务',
      creative:'发现 X 中文原帖，用 Zen 创作观点并生成原创图文素材'}[view]) :
    isPosts ? '批量管理草稿，逐条打开 X 编辑器，发布后登记实际帖子链接' :
    isDrafts ? '已保存的中文原创改写草稿，可继续编辑并加入发布队列' : '最近 24 小时的 X 中文原帖，结合互动量与发布时间动态排序';
  $('#breadcrumb-name').textContent = isWorkspace ? workspaceNames[view] :
    isPosts ? '待发布队列' : isDrafts ? '我的草稿' : categoryNames[category];
  document.querySelectorAll('.nav-btn').forEach((node) =>
    node.classList.toggle('active', isWorkspace ? node.id === view + '-nav' :
      isPosts ? node.id === 'posts-nav' :
      isDrafts ? node.id === 'drafts-nav' : node.dataset.category === category));
  if (isDrafts) loadDrafts().catch((err) => toast(err.message, true));
  else if (isPosts) loadQueue().catch((err) => toast(err.message, true));
  else if (view === 'chat') showChat().catch((err) => toast(err.message, true));
  else if (view === 'profile') showProfile().catch((err) => toast(err.message, true));
  else if (view === 'agent') showAgentWorkspace().catch((err) => toast(err.message, true));
  else if (view === 'creative') showCreative().catch((err) => toast(err.message, true));
  else loadTrends().catch((err) => toast(err.message, true));
}

async function openCreatorHubWorkspace() {
  const status = await api('/api/creatorhub/status');
  if (!status.installed) throw new Error('多平台运营组件尚未安装：' + status.path);
  const info = status.running ? status : await api('/api/creatorhub/start', {method: 'POST'});
  if (!info.running) throw new Error('多平台运营服务未能正常启动');
  window.location.assign(info.url.replace(/\/$/, '') + '/');
}

async function loadQueue() {
  const items = await api('/api/queue');
  if (state.view !== 'queue') return;
  state.queueItems = items;
  if (!items.length) {
    $('#cards').innerHTML = '<div class="empty-state"><div class="empty-icon">↗</div><h3>待发布队列还没有内容</h3><p>在草稿箱选择内容，加入队列后依次打开 X 官方编辑器。</p></div>';
    return;
  }
  $('#cards').innerHTML = `<div class="queue-toolbar">
    <span>共 ${items.length} 条任务</span>
    <span>待打开 ${items.filter((q) => q.status === 'queued').length} 条</span>
    <span>已打开 ${items.filter((q) => q.status === 'opened').length} 条</span>
    <button class="primary-button" data-action="open-next">打开下一条 ↗</button>
    <button class="outline-button" data-action="refresh-queue">↻ 刷新浏览器任务状态</button>
  </div>` + items.map((item) => `<article class="queue-card">
    <div class="queue-head"><span class="queue-status">${escapeHtml({
      queued:'● 等待审核发布', opened:'◷ 编辑器已打开', recorded:'✓ 已登记帖子链接', skipped:'↷ 暂时跳过',
    }[item.status])}</span><span class="queue-title">${escapeHtml(item.title || '草稿')} · ${relativeTime(item.created_at)}</span></div>
    <p>${escapeHtml(item.content)}</p>
    ${queueMediaMarkup(item)}
    <div class="queue-actions">
      ${['queued','opened'].includes(item.status) ? `<button class="primary-button" data-action="open-queue" data-id="${item.id}">打开 X 发帖窗口 ↗</button><button data-action="skip-queue" data-id="${item.id}">跳过</button>` : ''}
      ${item.pack_id ? `<a class="queue-link" href="/api/creative/packs/${item.pack_id}/download">下载三张配图 ↓</a>` : ''}
      ${['queued','opened'].includes(item.status) && item.attachments.some((photo) => photo.selected) ?
        `<button class="primary-button" data-action="prepare-media-browser" data-id="${item.id}"
          ${item.browser_preparation && ['queued','running','waiting_login','ready'].includes(item.browser_preparation.status) ? 'disabled' : ''}>
          自动填写图文到 X ↗</button>` : ''}
      ${item.attachments.length ? `<a class="queue-link" href="/api/queue/${item.id}/bundle">下载已选择的图文附件包 ↓</a>` : ''}
      ${item.status === 'opened' ? `<div class="queue-link-form"><input id="post-url-${item.id}" placeholder="发布后粘贴 X 帖子链接" type="url"><button data-action="record-queue" data-id="${item.id}">登记已发布</button></div>` : ''}
      ${item.status === 'skipped' || item.status === 'opened' ? `<button data-action="requeue" data-id="${item.id}">重新排队</button>` : ''}
      ${item.status === 'recorded' ? `<a class="queue-link" href="${escapeHtml(safeUrl(item.post_url))}" target="_blank" rel="noopener noreferrer">打开已登记的帖子 ↗</a>` : `<button data-action="remove-queue" data-id="${item.id}">移出队列</button>`}
    </div>
  </article>`).join('');
  await refreshQueueCount();
}

function queueMediaMarkup(item) {
  const choices = item.attachments || [];
  const ready = choices.filter((photo) => photo.ready);
  const selected = choices.filter((photo) => photo.selected);
  const sourceMedia = choices.some((photo) => photo.origin === 'source');
  const progress = item.browser_preparation;
  if (!choices.length) return '<div class="media-note">此条草稿还没有图片，可以在图文工厂生成原创图卡。</div>';
  const containsVideo = choices.some((photo) => photo.kind === 'video');
  const list = choices.map((photo) => `
    <div class="media-choice ${photo.selected ? 'selected' : ''} ${photo.ready ? '' : 'pending'}">
      <div class="media-choice-thumb ${photo.kind === 'video' ? 'video-thumb' : ''}">${photo.kind === 'video'
        ? `<video src="${escapeHtml(safeMediaUrl(photo.url))}" controls preload="metadata" playsinline aria-label="${escapeHtml(photo.label)}"></video>`
        : `<img loading="lazy" src="${escapeHtml(safeMediaUrl(photo.url))}" alt="${escapeHtml(photo.label)}">`}</div>
      <label class="media-choice-label"><input class="queue-media-checkbox" type="checkbox" data-id="${item.id}" value="${escapeHtml(photo.id)}"
        ${photo.selected ? 'checked' : ''} ${!photo.ready || item.status === 'recorded' ? 'disabled' : ''}>
        ${escapeHtml(photo.label)}</label>
      <small>${photo.kind === 'video' ? 'MP4 视频' :
        photo.origin === 'source' ? 'X 原帖图片' :
        photo.origin === 'generated' ? 'AI 原创图卡' : '本地图片'}${photo.ready ? '' : ' · 待导入'}</small>
    </div>`).join('');
  return `<div class="media-chooser">
    <div class="media-chooser-heading"><strong>媒体附件 · 已选 ${selected.length} 件</strong>
      <span>${containsVideo ? '每条帖子可选择一个视频' : '每条帖子最多四张图片'}</span></div>
    <div class="media-choice-grid">${list}</div>
    <div class="media-chooser-actions">
      ${sourceMedia ? `<button data-action="import-originals" data-id="${item.id}">↓ 导入 X 原帖图片</button>` : ''}
      ${ready.some((photo) => photo.origin === 'generated') && item.status !== 'recorded'
        ? `<button data-action="select-generated" data-id="${item.id}">选择原创三图</button>` : ''}
      <span>已选附件将自动加入浏览器编辑窗口</span>
    </div>
    ${progress ? `<div class="browser-prep-status">
      浏览器助手 · ${escapeHtml({
        queued:'等待启动',running:'正在打开 Edge',waiting_login:'等待登录 X',
        ready:'已填入文字与图片',closed:'浏览器窗口已关闭',failed:'任务出错',
      }[progress.status] || progress.status)} · ${escapeHtml(progress.detail || '')}
    </div>` : ''}
  </div>`;
}

async function loadDrafts() {
  const drafts = await api('/api/drafts');
  if (state.view !== 'drafts') return;
  state.drafts = drafts;
  if (!drafts.length) {
    $('#cards').innerHTML = '<div class="empty-state"><div class="empty-icon">✎</div><h3>草稿箱是空的</h3><p>找到感兴趣的话题，点击「AI 改编」生成内容。</p></div>';
    return;
  }
  $('#cards').innerHTML = `<div class="queue-toolbar"><label><input id="select-all-drafts" type="checkbox"> 全选</label>
    <span>选择需要发布的草稿</span><button class="primary-button" data-action="enqueue-selected">加入待发布队列 ↗</button></div>`
    + drafts.map((draft) => `<article class="draft-card">
    <div class="draft-heading"><input type="checkbox" class="draft-checkbox" value="${draft.id}"><h3>${escapeHtml(draft.title)} · ${relativeTime(draft.updated_at)}</h3></div><p>${escapeHtml(draft.content)}</p>
    <div class="draft-buttons"><button data-action="edit-draft" data-id="${draft.id}">✎ 继续编辑</button><button data-action="enqueue-draft" data-id="${draft.id}">加入队列</button><button data-action="copy-draft" data-id="${draft.id}">复制文本</button><button data-action="delete-draft" data-id="${draft.id}">删除草稿</button></div>
  </article>`).join('');
}

function openDrawer() {
  $('#drawer-overlay').classList.remove('hidden');
  $('#drawer').classList.add('open');
  $('#drawer').setAttribute('aria-hidden', 'false');
}

function closeDrawer() {
  $('#drawer-overlay').classList.add('hidden');
  $('#drawer').classList.remove('open');
  $('#drawer').setAttribute('aria-hidden', 'true');
}

function draftEditor(draft) {
  if (!draft) return '';
  const count = [...draft.content].length;
  return `<div class="result-header"><strong>✦ 已生成的内容</strong><span class="char-count ${count > 280 ? 'over' : ''}" id="char-count">${count} / 280</span></div>
    <label class="field" for="draft-text">编辑内容</label>
    <textarea id="draft-text" class="editor" spellcheck="true">${escapeHtml(draft.content)}</textarea>
    <div class="draft-actions"><button class="outline-button" data-action="save">保存修改</button><button class="outline-button" data-action="copy">复制文本</button><button class="primary-button" data-action="enqueue-current">加入待发布队列 ↗</button></div>
    <p class="studio-note">队列逐条打开 X 官方编辑器，由你点击发布。发布完成后可登记真实帖子链接。</p>`;
}

function showComposer(item) {
  state.selected = item;
  state.draft = null;
  $('#drawer-body').innerHTML = `
    <div class="selected-topic"><small>正在创作 · ${escapeHtml(categoryNames[item.category] || item.category)}</small>
      <h3>${escapeHtml(item.title)}</h3><a href="${escapeHtml(safeUrl(item.url))}" target="_blank" rel="noopener noreferrer">打开 X 原帖与作者 ↗</a></div>
    <div class="drawer-row"><div><label class="field" for="style">内容风格</label><select id="style" class="select-field">
      <option value="opinion">🔥 强观点</option><option value="explain">💡 通俗科普</option><option value="humor">😄 轻松幽默</option><option value="question">💬 引发讨论</option><option value="reply">🗣️ 热点评论</option><option value="thread">🧵 短串文</option>
    </select></div><div><label class="field" for="language">发帖语言</label><select id="language" class="select-field"><option value="zh">简体中文</option><option value="en">English</option></select></div></div>
    <label class="field" for="angle">你希望加入的观点（可选）</label>
    <input id="angle" class="text-field" maxlength="300" placeholder="例如：从用户体验、争议或商业影响切入">
    <div class="drawer-row"><div><label class="field" for="compose-model">创作模型</label><select id="compose-model" class="select-field"></select></div>
      <div><label class="field" for="compose-effort">思考强度</label><select id="compose-effort" class="select-field"></select></div></div>
    <button id="generate-button" class="primary-button full-width" data-action="generate">✦ 调用 AI 生成原创改编</button>
    <p class="studio-note">系统依据 X 原帖生成新观点与文字，原作者及原帖链接始终保留在工作台中。</p>
    <div id="draft-editor"><div class="result-header"><strong>或直接手动写作</strong></div>
      <label class="field" for="manual-text">你的原创观点</label>
      <textarea id="manual-text" class="editor" placeholder="写下观点、争议、发现或自己做过的实测..."></textarea>
      <button class="outline-button full-width" data-action="manual">保存手写草稿</button>
    </div>`;
  openDrawer();
  zenAttachComposer();
}

function showExistingDraft(draft) {
  state.selected = null;
  state.draft = draft;
  $('#drawer-body').innerHTML = `<div class="selected-topic"><small>已保存草稿</small><h3>${escapeHtml(draft.title)}</h3></div>
    <div id="draft-editor">${draftEditor(draft)}</div>`;
  openDrawer();
}

async function generateDraft() {
  const button = $('#generate-button');
  button.disabled = true;
  button.textContent = '正在调用模型生成...';
  try {
    state.draft = await api('/api/drafts/generate', {
      method: 'POST',
      body: JSON.stringify({ trend_id: state.selected.id, style: $('#style').value,
        language: $('#language').value, angle: $('#angle').value,
        model: $('#compose-model').value, effort: $('#compose-effort').value }),
    });
    $('#draft-editor').innerHTML = draftEditor(state.draft);
    await overview();
    const cost = state.draft.generation?.usage?.cost_usd;
    toast('内容已生成并保存 · ' + state.draft.generation.model +
      (cost !== null && cost !== undefined ? ' · $' + Number(cost).toFixed(6) : ''));
  } catch (err) {
    toast(err.message, true);
  } finally {
    button.disabled = false;
    button.textContent = '✦ 再生成一个版本';
  }
}

async function saveManual() {
  const content = $('#manual-text').value.trim();
  if (!content) { toast('请先输入内容', true); return; }
  state.draft = await api('/api/drafts', {
    method: 'POST',
    body: JSON.stringify({trend_id: state.selected.id, content, language: $('#language').value}),
  });
  $('#draft-editor').innerHTML = draftEditor(state.draft);
  await overview();
  toast('手写草稿已保存');
}

async function saveCurrent() {
  if (!state.draft) return;
  await api('/api/drafts/' + state.draft.id, {
    method: 'PUT', body: JSON.stringify({ content: $('#draft-text').value }),
  });
  state.draft.content = $('#draft-text').value;
  toast('草稿已保存');
  if (state.view === 'drafts') await loadDrafts();
}

async function copyText(text) {
  await navigator.clipboard.writeText(text);
  toast('已复制到剪贴板');
}

async function enqueueIds(draftIds) {
  const items = await api('/api/queue', {
    method: 'POST', body: JSON.stringify({draft_ids: draftIds}),
  });
  await refreshQueueCount();
  toast('已加入待发布队列：' + items.length + ' 条');
  closeDrawer();
  setView('queue');
}

async function openQueueItem(itemId) {
  const popup = window.open('about:blank', '_blank');
  if (!popup) throw new Error('浏览器阻止了新窗口，请允许 XHotLab 打开新标签页');
  try {
    const result = await api('/api/queue/' + itemId + '/open', {method:'POST'});
    popup.location.href = result.compose_url;
    toast('已打开 X 编辑器，发布后请登记实际帖子链接');
    await loadQueue();
  } catch (err) {
    popup.close();
    throw err;
  }
}

async function openNext() {
  const next = (state.queueItems || []).find((item) => item.status === 'queued');
  if (!next) { toast('待打开的草稿已全部处理'); return; }
  await openQueueItem(next.id);
}

function openSettings() {
  openZenSettings();
}

async function refreshAll() {
  const button = $('#refresh-button');
  button.disabled = true;
  button.classList.add('is-refreshing');
  try {
    const result = await api('/api/refresh', {method: 'POST'});
    await overview();
    if (state.view === 'trends') await loadTrends();
    toast(`扫描完成，成功读取 ${result.ok} 个数据源，共 ${result.items} 条条目`);
  } catch (err) {
    toast(err.message, true);
  } finally {
    button.disabled = false;
    button.classList.remove('is-refreshing');
  }
}

document.querySelectorAll('[data-category]').forEach((button) => button.addEventListener('click', () => setView('trends', button.dataset.category)));
$('#drafts-nav').addEventListener('click', () => setView('drafts'));
$('#posts-nav').addEventListener('click', () => setView('queue'));
$('#queue-shortcut').addEventListener('click', () => setView('queue'));
$('#creative-shortcut').addEventListener('click', () => setView('creative'));
$('#creative-nav').addEventListener('click', () => setView('creative'));
$('#chat-shortcut').addEventListener('click', () => setView('chat'));
$('#chat-nav').addEventListener('click', () => setView('chat'));
$('#profile-nav').addEventListener('click', () => setView('profile'));
$('#agent-nav').addEventListener('click', () => setView('agent'));
$('#creatorhub-nav').addEventListener('click', () => setView('creatorhub'));
$('#creatorhub-shortcut').addEventListener('click', () => setView('creatorhub'));
$('#publish-nav').addEventListener('click', () => setView('publish'));
$('#publish-shortcut').addEventListener('click', () => setView('publish'));
$('#refresh-button').addEventListener('click', refreshAll);
$('#load-more').addEventListener('click', () => loadTrends(true).catch((err) => toast(err.message, true)));
let searchTimer;
$('#search').addEventListener('input', (event) => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    state.query = event.target.value.trim();
    if (state.view === 'trends') loadTrends().catch((err) => toast(err.message, true));
  }, 230);
});
document.querySelectorAll('[data-sort]').forEach((button) => button.addEventListener('click', () => {
  state.sort = button.dataset.sort;
  document.querySelectorAll('[data-sort]').forEach((node) => node.classList.toggle('active', node === button));
  loadTrends().catch((err) => toast(err.message, true));
}));

document.addEventListener('click', async (event) => {
  const button = event.target.closest('[data-action]');
  if (!button) return;
  const action = button.dataset.action;
  const id = button.dataset.id;
  try {
    if (action === 'compose') showComposer(state.items.find((item) => item.id === id));
    if (action === 'generate') await generateDraft();
    if (action === 'manual') await saveManual();
    if (action === 'edit-draft') showExistingDraft(state.drafts.find((draft) => draft.id === id));
    if (action === 'copy-draft') await copyText(state.drafts.find((draft) => draft.id === id).content);
    if (action === 'delete-draft' && window.confirm('确认删除这个草稿吗？')) {
      await api('/api/drafts/' + id, {method: 'DELETE'});
      await loadDrafts();
      await overview();
      toast('草稿已删除');
    }
    if (action === 'save') await saveCurrent();
    if (action === 'copy') await copyText($('#draft-text').value);
    if (action === 'enqueue-current') {
      await saveCurrent();
      await enqueueIds([state.draft.id]);
    }
    if (action === 'enqueue-draft') await enqueueIds([id]);
    if (action === 'enqueue-selected') {
      const ids = [...document.querySelectorAll('.draft-checkbox:checked')].map((node) => node.value);
      if (!ids.length) { toast('请勾选需要加入队列的草稿', true); return; }
      await enqueueIds(ids);
    }
    if (action === 'open-queue') await openQueueItem(id);
    if (action === 'open-next') await openNext();
    if (action === 'refresh-queue') await loadQueue();
    if (action === 'import-originals') {
      button.disabled = true;
      button.textContent = '正在导入图片…';
      const result = await api('/api/queue/' + id + '/media/import', {method:'POST'});
      toast('已经导入 ' + result.imported + ' 个原帖图片或视频封面');
      await loadQueue();
    }
    if (action === 'select-generated') {
      const item = state.queueItems.find((entry) => entry.id === id);
      const selected = item.attachments.filter((photo) =>
        photo.origin === 'generated' && photo.ready).map((photo) => photo.id);
      await api('/api/queue/' + id + '/media', {
        method:'PUT',body:JSON.stringify({media_ids:selected}),
      });
      await loadQueue();
      toast('已选择 ' + selected.length + ' 张原创图片');
    }
    if (action === 'prepare-media-browser') {
      if (!window.confirm('将在独立 Edge 窗口中填写文字并上传已选图片。首次使用需要登录 X，完成后由你点击发布。是否打开？')) return;
      const result = await api('/api/queue/' + id + '/prepare-browser', {method:'POST'});
      toast('浏览器图文助手已启动：' + result.id);
      await loadQueue();
    }
    if (action === 'record-queue') {
      await api('/api/queue/' + id + '/record', {method:'POST',
        body:JSON.stringify({post_url:$('#post-url-' + id).value.trim()})});
      toast('已登记你提供的实际帖子链接');
      await loadQueue();
    }
    if (action === 'skip-queue' || action === 'requeue') {
      await api('/api/queue/' + id + '/' + (action === 'skip-queue' ? 'skip' : 'requeue'), {method:'POST'});
      await loadQueue();
    }
    if (action === 'remove-queue' && window.confirm('将此草稿移出待发布队列？')) {
      await api('/api/queue/' + id, {method:'DELETE'});
      await loadQueue();
    }
  } catch (err) { toast(err.message, true); }
});

document.addEventListener('input', (event) => {
  if (event.target.id !== 'draft-text') return;
  const count = [...event.target.value].length;
  $('#char-count').textContent = `${count} / 280`;
  $('#char-count').classList.toggle('over', count > 280);
});
document.addEventListener('change', (event) => {
  if (event.target.id !== 'select-all-drafts') return;
  document.querySelectorAll('.draft-checkbox').forEach((node) => { node.checked = event.target.checked; });
});
document.addEventListener('change', async (event) => {
  if (!event.target.matches('.queue-media-checkbox')) return;
  const queueId = event.target.dataset.id;
  const ids = [...document.querySelectorAll('.queue-media-checkbox')]
    .filter((checkbox) => checkbox.dataset.id === queueId && checkbox.checked)
    .map((checkbox) => checkbox.value);
  if (ids.length > 4) {
    event.target.checked = false;
    toast('每条 X 帖子最多选择四张图片', true);
    return;
  }
  try {
    await api('/api/queue/' + queueId + '/media', {
      method:'PUT',body:JSON.stringify({media_ids:ids}),
    });
    await loadQueue();
    toast('图片附件已保存');
  } catch (error) {
    event.target.checked = !event.target.checked;
    toast(error.message, true);
  }
});

$('#close-drawer').addEventListener('click', closeDrawer);
$('#drawer-overlay').addEventListener('click', closeDrawer);
$('#settings-button').addEventListener('click', openSettings);
$('#top-settings').addEventListener('click', openSettings);
$('#close-settings').addEventListener('click', () => $('#settings-layer').classList.add('hidden'));
$('#settings-layer').addEventListener('click', (event) => {
  if (event.target.id === 'settings-layer') $('#settings-layer').classList.add('hidden');
});
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') { closeDrawer(); $('#settings-layer').classList.add('hidden'); }
});

document.addEventListener('DOMContentLoaded', () => {
  if (new URLSearchParams(window.location.search).get('view') === 'creatorhub') {
    openCreatorHubWorkspace().catch((err) => toast(err.message, true));
    return;
  }
  setView('publish');
  overview().then((info) => {
    if (!info.total) {
      setTimeout(() => overview().catch((err) => console.error('刷新首页统计失败', err)), 8000);
    }
  }).catch((err) => console.error('首页统计加载失败', err));
});

let automaticTrendRefreshActive = false;
async function refreshVisibleTrends() {
  if (automaticTrendRefreshActive || document.visibilityState !== 'visible'
      || state.view !== 'trends' || window.scrollY > 1200
      || $('#drawer').classList.contains('open')) return;
  automaticTrendRefreshActive = true;
  try {
    await overview();
    await loadTrends();
  } catch (error) {
    console.error('X 中文热门自动更新失败', error);
  } finally {
    automaticTrendRefreshActive = false;
  }
}
setInterval(refreshVisibleTrends, 3 * 60 * 1000);
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') {
    refreshVisibleTrends();
  }
});
