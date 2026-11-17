function renderCreativePack(pack) {
  const cards = pack.images.map((url, index) => (
    '<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener noreferrer" ' +
    'title="打开原始图卡"><img loading="lazy" src="' + escapeHtml(url) +
    '" alt="图文卡片 ' + (index + 1) + '"></a>'
  )).join('');
  const sourceMedia = (pack.source_media || []).map((entry) =>
    '<a href="' + escapeHtml(safeUrl(entry.original_url)) +
    '" target="_blank" rel="noopener noreferrer" title="查看原帖媒体来源">' +
    '<img loading="lazy" src="' + escapeHtml(safeMediaUrl(entry.url)) +
    '" alt="' + escapeHtml(entry.kind === 'photo' ? 'X 原帖图片' : 'X 原帖视频封面') +
    '"><small>' + (entry.kind === 'photo' ? '原帖图片' : '视频封面') + ' · ' +
    (entry.downloaded ? '已保存到本机' : '尚未下载') + '</small></a>'
  ).join('');
  return '<article class="creative-pack">' +
    '<div class="creative-pack-top"><span>✦ 已生成图文 · ' + escapeHtml(pack.source) +
    '</span><span>' + relativeTime(pack.created_at) + '</span></div>' +
    '<h3>' + escapeHtml(pack.headline) + '</h3>' +
    '<p class="creative-hook">' + escapeHtml(pack.hook) + '</p>' +
    '<div class="creative-gallery">' + cards + '</div>' +
    (sourceMedia ? '<div class="source-gallery-heading">X 原帖媒体资料 <small>来自原作者 · 点击查看来源</small></div>' +
      '<div class="source-gallery">' + sourceMedia + '</div>' : '') +
    '<p class="creative-copy">' + escapeHtml(pack.content) + '</p>' +
    '<div class="creative-actions">' +
    '<a class="primary-button" href="/api/creative/packs/' + pack.id +
    '/download">下载完整图文 ZIP ↓</a>' +
    '<a class="outline-button" href="' + escapeHtml(safeUrl(pack.source_url)) +
    '" target="_blank" rel="noopener noreferrer">查看 X 原帖 ↗</a>' +
    '<button class="outline-button" data-creative-action="open-queue">进入发布队列 ↗</button>' +
    '</div></article>';
}

async function showCreative() {
  const [status, packs] = await Promise.all([
    api('/api/creative/status'), api('/api/creative/packs'),
  ]);
  const statusName = status.enabled ? '● 已启用定时生成' : '○ 已关闭定时生成';
  const recentRuns = status.runs.slice(0, 6).map((run) =>
    '<div class="creative-run"><span>' + escapeHtml(run.status === 'completed' ?
      '✓ 已完成' : run.status === 'running' ? '◷ 正在生成' : '⚠ 运行失败') +
    '</span><span>' + escapeHtml(run.started_at) + '</span><strong>' +
    run.produced + ' 套</strong></div>'
  ).join('');
  $('#cards').innerHTML =
    '<div class="creative-studio">' +
      '<div class="creative-control">' +
        '<div class="mini-eyebrow">OPEN SOURCE CONTENT FACTORY</div>' +
        '<h3>自动发现 X 中文热门帖子，创作中文观点与图文</h3>' +
        '<p>读取 X 公开原帖、作者、照片及互动数据，Zen 负责原创观点与写稿，ClickClick 渲染高清 PNG。自动保存原帖媒体，素材包保留来源链接。</p>' +
        '<div class="creative-stats">' +
          '<span>' + statusName + '</span>' +
          '<span>北京时间 ' + status.scheduled_at.join(' / ') + '</span>' +
          '<span>每次 ' + status.per_run + ' 个选题</span>' +
          '<span>当日已用 $' + status.cost_today_usd.toFixed(5) +
            ' / $' + status.max_daily_cost_usd.toFixed(2) + '</span>' +
        '</div>' +
        '<div class="creative-manual">' +
          '<label>本次生成数量 <select id="creative-count" class="select-field">' +
          '<option value="1">1 套</option><option value="2" selected>2 套</option>' +
          '<option value="3">3 套</option></select></label>' +
          '<button class="primary-button" data-creative-action="run">✦ 立即生成真实图文</button>' +
          '<button class="outline-button" data-creative-action="refresh">↻ 刷新记录</button>' +
        '</div>' +
        '<div id="creative-message" class="creative-message"></div>' +
      '</div>' +
      '<div class="creative-progress"><strong>最近运行记录</strong>' +
        (recentRuns || '<p>首次定时任务将在计划时段执行。</p>') + '</div>' +
    '</div>' +
    '<div class="creative-gallery-title"><h3>已生成的图文内容</h3>' +
      '<span>' + packs.length + ' 套 X 中文原帖衍生素材</span></div>' +
    (packs.length ? packs.map(renderCreativePack).join('') :
      '<div class="empty-state"><h3>还没有生成的图文内容</h3><p>点击「立即生成真实图文」体验完整的开源组件生产流程。</p></div>');
}

document.addEventListener('click', async (event) => {
  const target = event.target.closest('[data-creative-action]');
  if (!target) return;
  const action = target.dataset.creativeAction;
  if (action === 'open-queue') {
    setView('queue');
    return;
  }
  if (action === 'refresh') {
    await showCreative();
    return;
  }
  if (action !== 'run') return;
  target.disabled = true;
  target.textContent = '正在生成图文…';
  $('#creative-message').textContent = '正在挑选 X 中文原帖、生成原创观点与 PNG 图卡…';
  try {
    const result = await api('/api/creative/run', {
      method: 'POST',
      body: JSON.stringify({count:Number($('#creative-count').value),refresh:false}),
    });
    toast('本次完成 ' + result.produced + ' 套真实图文');
    await showCreative();
  } catch (error) {
    $('#creative-message').textContent = error.message;
    toast(error.message, true);
    target.disabled = false;
    target.textContent = '✦ 立即生成真实图文';
  }
});
