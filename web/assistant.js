let zenCatalog = null;
let zenPreferences = null;
let currentChatId = null;
let profileSuggestion = '';
let forwardedAgentTask = '';

function displayPrice(number) {
  return Number.isFinite(Number(number)) ? '$' + Number(number).toFixed(3) : '价格未提供';
}

function modelsForSelect() {
  return zenCatalog?.models || [];
}

function modelById(id) {
  return modelsForSelect().find((model) => model.id === id);
}

function updateModelOptions(selector, preferred, allowNative = false) {
  const select = $(selector);
  if (!select) return;
  const values = modelsForSelect();
  select.innerHTML = (allowNative ? '<option value="">本机 CLI 默认模型</option>' : '') +
    values.map((model) => `<option value="${escapeHtml(model.id)}"
      ${model.free_restricted ? 'disabled' : ''}>${escapeHtml(model.name)} · ${displayPrice(model.input_price)}/${displayPrice(model.output_price)} 每百万 tokens${model.free_restricted ? ' · 平台内限定' : ''}</option>`).join('');
  if (preferred && [...select.options].some((option) => option.value === preferred && !option.disabled)) {
    select.value = preferred;
  } else if (!allowNative) {
    select.value = values.find((model) => model.id === 'glm-5.3-flash')?.id ||
      values.find((model) => !model.free_restricted)?.id || '';
  } else {
    select.value = '';
  }
}

function updateEffortOptions(modelSelector, effortSelector, preferred = 'none') {
  const select = $(effortSelector);
  if (!select) return;
  const model = modelById($(modelSelector)?.value);
  const strengths = model?.efforts || [];
  const labels = {
    none: '自动 · 模型默认', minimal: '极低', low: '低', medium: '中',
    high: '高', xhigh: '极高', max: '最高',
  };
  select.innerHTML = ['none', ...strengths.filter((value) => value !== 'none')]
    .map((value) => `<option value="${value}">${labels[value] || value}</option>`).join('');
  select.value = [...select.options].some((option) => option.value === preferred) ? preferred : 'none';
}

function modelCatalogRow(model) {
  const price = model.input_price === null ? '价格待核实' :
    (model.free_restricted ? '仅限 OpenCode 使用' :
      `输入 ${displayPrice(model.input_price)} · 输出 ${displayPrice(model.output_price)} / 百万 tokens`);
  const strengths = model.efforts.length ? model.efforts.join(' / ') :
    (model.reasoning ? '模型自行管理' : '无需额外思考设置');
  return `<article class="model-entry">
    <div><strong>${escapeHtml(model.name)}</strong><small>${escapeHtml(model.id)} · ${escapeHtml(model.native_api || 'chat')}</small></div>
    <div><div class="model-entry-price">${escapeHtml(price)}</div>
      <span>上下文 ${model.context ? Math.round(model.context / 1000) + 'K' : '未知'} · 思考：${escapeHtml(strengths)}</span></div>
  </article>`;
}

function renderModelCatalog() {
  const search = ($('#model-search')?.value || '').toLowerCase().trim();
  const items = modelsForSelect().filter((model) =>
    (model.name + ' ' + model.id + ' ' + model.family).toLowerCase().includes(search));
  $('#model-count').textContent = `(${items.length}/${modelsForSelect().length})`;
  $('#model-catalog').innerHTML = items.map(modelCatalogRow).join('');
}

async function initZen(refresh = false) {
  const [catalog, options] = await Promise.all([
    refresh ? api('/api/zen/models/refresh', {method:'POST'}) : api('/api/zen/models'),
    api('/api/zen/settings'),
  ]);
  zenCatalog = catalog;
  zenPreferences = options;
  updateModelOptions('#default-compose-model', options.compose_model);
  updateModelOptions('#default-chat-model', options.chat_model);
  updateEffortOptions('#default-compose-model', '#default-compose-effort', options.compose_effort);
  updateEffortOptions('#default-chat-model', '#default-chat-effort', options.chat_effort);
  $('#zen-plan').value = options.plan;
  $('#zen-status').textContent = `${options.key_configured ? '● Zen 密钥已连接' : '○ 等待连接 Zen 密钥'} ·
    已导入 ${catalog.total} 个模型 · 更新于 ${new Date(catalog.updated_at).toLocaleString('zh-CN')}`;
  renderModelCatalog();
  return catalog;
}

async function openZenSettings() {
  $('#settings-layer').classList.remove('hidden');
  try {
    await initZen();
    const usage = await api('/api/zen/usage');
    $('#zen-status').textContent += ` · 已记录费用 ${displayPrice(usage.total_cost_usd || 0)}`;
  } catch (error) {
    $('#zen-status').textContent = '模型目录读取失败：' + error.message;
    toast(error.message, true);
  }
}

async function zenAttachComposer() {
  if (!zenCatalog) await initZen();
  updateModelOptions('#compose-model', zenPreferences.compose_model);
  updateEffortOptions('#compose-model', '#compose-effort', zenPreferences.compose_effort);
}

function chatMessageHtml(message) {
  return `<div class="chat-line ${message.role === 'user' ? 'mine' : 'assistant'}">
    <div class="chat-avatar">${message.role === 'user' ? '我' : '✦'}</div>
    <div class="chat-bubble"><div class="chat-author">${message.role === 'user' ? '你' : 'XHotLab Assistant'}</div>
      <div class="chat-text">${escapeHtml(message.content)}</div></div>
  </div>`;
}

async function showChat() {
  if (!zenCatalog) await initZen();
  let chats = await api('/api/chats');
  if (!currentChatId) {
    if (!chats.length) {
      const created = await api('/api/chats', {method:'POST', body: JSON.stringify({
        model:zenPreferences.chat_model, effort:zenPreferences.chat_effort,
      })});
      currentChatId = created.id;
      chats = [created];
    } else {
      currentChatId = chats[0].id;
    }
  }
  const conversation = await api('/api/chats/' + currentChatId);
  $('#cards').innerHTML = `<div class="chat-layout">
    <aside class="chat-sessions">
      <button class="primary-button full-width" data-zen-action="new-chat">＋ 新建对话</button>
      <div class="chat-list-title">最近的对话</div>
      <div id="chat-session-list">${chats.map((chat) => `
        <button class="chat-session ${chat.id === currentChatId ? 'active' : ''}" data-zen-action="switch-chat"
          data-id="${chat.id}">${escapeHtml(chat.title)}</button>`).join('')}</div>
      <div class="chat-sidebar-foot">聊天记录保存在本机 SQLite 数据库。</div>
    </aside>
    <div class="chat-panel">
      <div class="chat-panel-header">
        <div class="chat-model-line"><label>当前模型<select class="select-field" id="chat-model"></select></label>
          <label>思考强度<select class="select-field" id="chat-effort"></select></label></div>
        <div class="chat-context-switches">
          <label><input id="chat-use-profile" type="checkbox" checked> 使用创作者背景</label>
          <label><input id="chat-use-trends" type="checkbox" checked> 参考实时热点</label>
        </div>
      </div>
      <div class="chat-history" id="chat-history">
        ${conversation.messages.length ? conversation.messages.map(chatMessageHtml).join('') :
          `<div class="chat-welcome"><div class="welcome-mark">✦</div><h3>今晚想聊点什么？</h3>
          <p>让 AI 帮你挑热点、判断传播潜力、拆解写作角度，也能将需要操作电脑的任务交给 Agent。</p>
          <div class="chat-suggestions"><button data-zen-action="suggest-chat" data-text="从最新热点里选出今天最值得写的五个，说明原因。">✦ 今天值得写什么</button>
          <button data-zen-action="suggest-chat" data-text="帮我设计一个适合新账号的热点互动方案，兼顾传播潜力与内容质量。">✧ 涨粉思路</button>
          <button data-zen-action="suggest-chat" data-text="分析我现在的内容生产流程，找出可以提高效率和原创性的环节。">⌘ 优化流程</button></div></div>`}
      </div>
      <div class="chat-compose">
        <textarea id="chat-input" rows="3" placeholder="聊聊热点、运营策略，或让 AI 帮你改写一条帖子…"></textarea>
        <div class="chat-compose-actions"><button class="outline-button" data-zen-action="chat-to-agent">⌘ 交给 Agent 操作</button>
          <span id="chat-usage" class="chat-usage">支持多轮对话</span><button class="primary-button" id="send-chat" data-zen-action="send-chat">发送 ↗</button></div>
      </div>
    </div>
  </div>`;
  updateModelOptions('#chat-model', conversation.model || zenPreferences.chat_model);
  updateEffortOptions('#chat-model', '#chat-effort', conversation.effort || zenPreferences.chat_effort);
  $('#chat-history').scrollTop = $('#chat-history').scrollHeight;
}

async function sendChat() {
  const input = $('#chat-input');
  const message = input.value.trim();
  if (!message) { toast('请输入聊天内容', true); return; }
  const settings = {
    model: $('#chat-model').value, effort: $('#chat-effort').value,
    include_profile: $('#chat-use-profile').checked,
    include_trends: $('#chat-use-trends').checked,
  };
  const button = $('#send-chat');
  button.disabled = true;
  button.textContent = '思考中…';
  $('#chat-history').insertAdjacentHTML('beforeend', chatMessageHtml({role:'user',content:message}));
  input.value = '';
  try {
    const result = await api('/api/chats/' + currentChatId + '/send', {
      method:'POST', body:JSON.stringify({...settings, text:message}),
    });
    $('#chat-history').insertAdjacentHTML('beforeend',
      chatMessageHtml({role:'assistant',content:result.text}));
    const price = result.usage.cost_usd;
    $('#chat-usage').textContent = result.model +
      (price === null || price === undefined ? '' : ' · 本次 $' + Number(price).toFixed(6));
    $('#chat-history').scrollTop = $('#chat-history').scrollHeight;
    const chats = await api('/api/chats');
    $('#chat-session-list').innerHTML = chats.map((chat) => `
      <button class="chat-session ${chat.id === currentChatId ? 'active' : ''}" data-zen-action="switch-chat"
       data-id="${chat.id}">${escapeHtml(chat.title)}</button>`).join('');
  } catch (error) {
    $('#chat-history').insertAdjacentHTML('beforeend',
      `<div class="chat-error">请求失败：${escapeHtml(error.message)}</div>`);
    toast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = '发送 ↗';
  }
}

async function showProfile() {
  const result = await api('/api/profile');
  $('#cards').innerHTML = `<div class="profile-layout">
    <article class="workspace-card">
      <span class="mini-eyebrow">CREATOR CONTEXT</span><h3>你的创作背景</h3>
      <p>对话和写稿时可使用你授权保存的背景，例如运营目标、受众、表达习惯、已有资源和内容偏好。</p>
      <label class="profile-toggle"><input id="profile-enabled" type="checkbox" ${result.enabled ? 'checked' : ''}> 在聊天与 AI 写稿中使用此背景</label>
      <textarea id="profile-text" rows="13" maxlength="6000">${escapeHtml(result.content)}</textarea>
      <div class="form-footer"><span>资料保存在这台电脑上，可以随时修改。</span>
        <button class="primary-button" data-zen-action="save-profile">保存背景资料</button></div>
    </article>
    <article class="workspace-card">
      <span class="mini-eyebrow">CONTEXT IMPORT</span><h3>从聊天与资料中提取背景</h3>
      <p>粘贴你希望用于创作的背景描述，也可以让模型阅读 XHotLab 中已有的用户聊天记录。生成的建议先展示给你确认。</p>
      <textarea id="profile-input" rows="7" placeholder="例如：我的账号面向英语用户，希望做多领域热点解读；我有编程和 AI 工程背景，偏好短句、有观点的内容…"></textarea>
      <button class="outline-button full-width" data-zen-action="suggest-profile">✦ AI 提取创作背景</button>
      <div id="profile-suggestion" class="profile-suggestion hidden">
        <label class="field">AI 建议资料（可编辑）</label>
        <textarea id="profile-proposal" rows="9"></textarea>
        <button class="primary-button full-width" data-zen-action="apply-profile">将建议保存为背景资料</button>
      </div>
    </article>
  </div>`;
}

async function showAgentWorkspace() {
  if (!zenCatalog) await initZen();
  const [available, jobs] = await Promise.all([
    api('/api/agents/availability'), api('/api/agents/jobs'),
  ]);
  $('#cards').innerHTML = `<div class="agent-layout">
    <article class="workspace-card">
      <span class="mini-eyebrow">LOCAL AGENT HARNESS</span><h3>交给本机 Agent 执行</h3>
      <p>运行 Codex 或 Claude Code，使用原有账号或 Zen 模型。指定工作目录和权限后启动，操作结果由本机独立进程保存。</p>
      <div class="agent-availability">Codex ${available.installed.codex ? '● 已安装' : '○ 未安装'} ·
        Claude Code ${available.installed.claude ? '● 已安装' : '○ 未安装'}</div>
      <div class="zen-form-grid">
        <label>执行工具<select class="select-field" id="agent-provider"><option value="codex">Codex CLI</option><option value="claude">Claude Code CLI</option></select></label>
        <label>模型认证<select class="select-field" id="agent-connection"><option value="zen">OpenCode Zen API</option><option value="native">本机 CLI 现有账号</option></select></label>
        <label>使用模型<select class="select-field" id="agent-model"></select></label>
        <label>思考强度<select class="select-field" id="agent-effort"></select></label>
        <label>文件操作权限<select class="select-field" id="agent-mode">
          <option value="read-only">只读分析</option><option value="workspace-write">允许修改工作目录</option>
        </select></label>
        <label>工作目录<input class="text-field" id="agent-workdir" value="${escapeHtml(available.default_workdir)}"></label>
      </div>
      <label class="field">Agent 任务说明</label>
      <textarea id="agent-task" rows="6" maxlength="12000" placeholder="例如：检查 XHotLab 的热点排序逻辑，找出有影响的算法问题，并给出改进建议与测试依据。"></textarea>
      <label class="profile-toggle"><input id="agent-approved" type="checkbox"> 我确认启动此本机任务，并授权所选目录和文件操作权限</label>
      <button class="primary-button full-width" data-zen-action="start-agent">⌘ 启动 Agent 任务</button>
      <p class="studio-note">本机任务最多运行 15 分钟。可随时点击右侧刷新查看运行结果，已启用独立进程保存任务。</p>
    </article>
    <article class="workspace-card">
      <div class="agent-jobs-heading"><div><span class="mini-eyebrow">TASK HISTORY</span><h3>任务记录</h3></div>
        <button class="outline-button" data-zen-action="refresh-agent">↻ 刷新状态</button></div>
      <div id="agent-jobs">${agentJobsHtml(jobs)}</div>
    </article>
  </div>`;
  if (forwardedAgentTask) {
    $('#agent-task').value = forwardedAgentTask;
    forwardedAgentTask = '';
  }
  updateModelOptions('#agent-model', zenPreferences.chat_model, true);
  $('#agent-connection').value = 'zen';
  setAgentConnection();
}

function agentJobsHtml(jobs) {
  if (!jobs.length) return '<div class="no-jobs">还没有任务。启动后会显示运行状态和实际输出。</div>';
  return jobs.slice(0, 20).map((job) => `<article class="agent-job">
    <div class="agent-job-head"><strong>${escapeHtml(job.provider)} · ${escapeHtml(job.connection)}</strong>
      <span class="agent-job-status ${escapeHtml(job.status)}">${escapeHtml({
        queued:'等待启动',running:'正在执行',completed:'已完成',failed:'执行失败',
      }[job.status] || job.status)}</span></div>
    <p>${escapeHtml(job.task)}</p>
    <small>${escapeHtml(job.mode)} · ${escapeHtml(job.model || '默认模型')} · ${relativeTime(job.created_at)}</small>
    ${job.result ? `<pre class="agent-output">${escapeHtml(job.result)}</pre>` : ''}
    ${job.error ? `<pre class="agent-output error">${escapeHtml(job.error)}</pre>` : ''}
    ${['completed','failed'].includes(job.status) ? `<button class="outline-button" data-zen-action="delete-agent-job" data-id="${job.id}">删除任务记录</button>` : ''}
  </article>`).join('');
}

function setAgentConnection() {
  const native = $('#agent-connection').value === 'native';
  updateModelOptions('#agent-model', native ? '' : zenPreferences.chat_model, native);
  updateEffortOptions('#agent-model', '#agent-effort', native ? 'none' : zenPreferences.chat_effort);
}

document.addEventListener('change', (event) => {
  const id = event.target.id;
  const related = {
    'default-compose-model': ['#default-compose-model','#default-compose-effort'],
    'default-chat-model': ['#default-chat-model','#default-chat-effort'],
    'compose-model': ['#compose-model','#compose-effort'],
    'chat-model': ['#chat-model','#chat-effort'],
    'agent-model': ['#agent-model','#agent-effort'],
  };
  if (related[id]) updateEffortOptions(...related[id]);
  if (id === 'agent-connection') setAgentConnection();
});

document.addEventListener('click', async (event) => {
  const target = event.target.closest('[data-zen-action]');
  if (!target) return;
  const action = target.dataset.zenAction;
  try {
    if (action === 'new-chat') {
      const result = await api('/api/chats', {method:'POST', body:JSON.stringify({
        model:zenPreferences.chat_model, effort:zenPreferences.chat_effort,
      })});
      currentChatId = result.id;
      await showChat();
    }
    if (action === 'switch-chat') { currentChatId = target.dataset.id; await showChat(); }
    if (action === 'suggest-chat') { $('#chat-input').value = target.dataset.text; $('#chat-input').focus(); }
    if (action === 'send-chat') await sendChat();
    if (action === 'chat-to-agent') {
      forwardedAgentTask = $('#chat-input').value.trim();
      setView('agent');
    }
    if (action === 'save-profile') {
      await api('/api/profile', {method:'PUT', body:JSON.stringify({
        content:$('#profile-text').value, enabled:$('#profile-enabled').checked,
      })});
      toast('背景资料已保存');
    }
    if (action === 'suggest-profile') {
      target.disabled = true;
      target.textContent = '正在整理背景…';
      const proposal = await api('/api/profile/suggest', {method:'POST',
        body:JSON.stringify({additional_context:$('#profile-input').value})});
      profileSuggestion = proposal.text;
      $('#profile-proposal').value = proposal.text;
      $('#profile-suggestion').classList.remove('hidden');
      target.disabled = false;
      target.textContent = '✦ 重新提取背景';
    }
    if (action === 'apply-profile') {
      await api('/api/profile', {method:'PUT', body:JSON.stringify({
        content:$('#profile-proposal').value, enabled:true,
      })});
      toast('确认后的背景建议已保存');
      await showProfile();
    }
    if (action === 'refresh-agent') {
      const jobs = await api('/api/agents/jobs');
      $('#agent-jobs').innerHTML = agentJobsHtml(jobs);
    }
    if (action === 'delete-agent-job') {
      if (!window.confirm('确认删除这条已经结束的 Agent 任务记录？')) return;
      await api('/api/agents/jobs/' + target.dataset.id, {method:'DELETE'});
      $('#agent-jobs').innerHTML = agentJobsHtml(await api('/api/agents/jobs'));
      toast('任务记录已删除');
    }
    if (action === 'start-agent') {
      const accepted = $('#agent-approved').checked;
      if (!accepted) throw new Error('请先确认启动任务和操作权限');
      const result = await api('/api/agents/jobs', {method:'POST', body:JSON.stringify({
        provider:$('#agent-provider').value,
        connection:$('#agent-connection').value,
        model:$('#agent-model').value || null,
        effort:$('#agent-effort').value,
        mode:$('#agent-mode').value,
        workdir:$('#agent-workdir').value.trim(),
        task:$('#agent-task').value.trim(),
        approved:accepted,
      })});
      toast('Agent 任务已提交：' + result.id);
      await showAgentWorkspace();
    }
  } catch (error) {
    toast(error.message, true);
    if (action === 'suggest-profile') {
      target.disabled = false;
      target.textContent = '✦ AI 提取创作背景';
    }
  }
});

$('#model-search').addEventListener('input', renderModelCatalog);
$('#settings-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  try {
    if ($('#zen-key').value.trim()) {
      await api('/api/zen/key', {method:'POST', body:JSON.stringify({api_key:$('#zen-key').value.trim()})});
    }
    await api('/api/zen/settings', {method:'PUT', body:JSON.stringify({
      plan:$('#zen-plan').value,
      chat_model:$('#default-chat-model').value,
      chat_effort:$('#default-chat-effort').value,
      compose_model:$('#default-compose-model').value,
      compose_effort:$('#default-compose-effort').value,
    })});
    $('#zen-key').value = '';
    await initZen();
    toast('Zen API 与模型设置已保存');
  } catch (error) { toast(error.message, true); }
});
$('#refresh-models').addEventListener('click', async () => {
  try {
    const result = await initZen(true);
    toast('已从 OpenCode 官方导入 ' + result.total + ' 个模型');
  } catch (error) { toast(error.message, true); }
});
$('#test-api').addEventListener('click', async () => {
  $('#zen-status').textContent = '正在使用默认写稿模型验证真实推理请求…';
  try {
    const response = await api('/api/zen/test', {method:'POST'});
    $('#zen-status').textContent = '● Zen 模型连通成功 · ' + response.model +
      ' · 本次成本 ' + displayPrice(response.usage.cost_usd || 0);
    toast('Zen 模型测试成功：' + response.text);
  } catch (error) {
    $('#zen-status').textContent = '连接失败：' + error.message;
    toast(error.message, true);
  }
});

initZen().catch((error) => {
  $('#zen-status').textContent = '获取模型目录失败：' + error.message;
});
if (new URLSearchParams(window.location.search).get('setup') === 'zen') {
  openZenSettings();
}
