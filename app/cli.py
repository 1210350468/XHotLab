import argparse
import asyncio
import json
import webbrowser

from . import agent_launch, browser_publish, creative, llm, store, xsource, zen


def output(value: dict | list) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='python -m app.cli',
        description='XHotLab：公开热点扫描、内容生产、待发布队列和浏览器人工发布',
    )
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('status', help='查看数据库和待发布队列状态')
    commands.add_parser('scan', help='搜索 X 中文社区真实热门帖子')

    hot = commands.add_parser('hot', help='查看真实热点')
    hot.add_argument('--category', default='all')
    hot.add_argument('--count', type=int, default=10)

    prepare = commands.add_parser('prepare', help='用已有 LLM API 生成原创草稿并加入待发布队列')
    prepare.add_argument('--count', type=int, default=5)
    prepare.add_argument('--category', default='all')
    prepare.add_argument('--style', choices=tuple(llm.STYLES), default='opinion')
    prepare.add_argument('--language', choices=('en', 'zh'), default='zh')
    prepare.add_argument('--model', default=None, help='选择已导入的 Zen 模型 ID')
    prepare.add_argument('--effort', default=None, help='思考强度，例如 low、high、max、none')

    models = commands.add_parser('models', help='列出官方 Zen 模型及价格')
    models.add_argument('--search', default='')

    run_agent = commands.add_parser('agent-run', help='启动已授权的本机 Codex 或 Claude Code')
    run_agent.add_argument('--provider', choices=('codex', 'claude'), required=True)
    run_agent.add_argument('--connection', choices=('zen', 'native'), default='zen')
    run_agent.add_argument('--model', default=None)
    run_agent.add_argument('--effort', default='none')
    run_agent.add_argument('--mode', choices=('read-only', 'workspace-write'), default='read-only')
    run_agent.add_argument('--workdir', default='')
    run_agent.add_argument('--approve', action='store_true', required=True)
    run_agent.add_argument('task')
    commands.add_parser('agent-jobs', help='列出 Agent 执行记录')
    commands.add_parser('creative-status', help='查看自动图文工厂的定时任务和每日费用')
    commands.add_parser('creative-packs', help='查看已完成的真实图文素材包')
    creative_run = commands.add_parser('creative-run', help='从真实中文热榜生成图文及发布队列')
    creative_run.add_argument('--count', type=int, default=2)
    creative_run.add_argument('--refresh', action='store_true')

    enqueue = commands.add_parser('enqueue', help='将现有草稿加入队列')
    enqueue.add_argument('draft_ids', nargs='+')
    commands.add_parser('queue', help='列出待发布队列')
    commands.add_parser('open-next', help='使用默认浏览器打开下一条 X 官方编辑窗口')

    record = commands.add_parser('record', help='保存人工完成发布的真实帖子链接')
    record.add_argument('queue_id')
    record.add_argument('post_url')
    return parser


async def prepare_posts(args) -> None:
    if not zen.get_api_key():
        raise ValueError('请在 XHotLab 模型设置中配置已有的 LLM API Key')
    if args.count < 1 or args.count > 30:
        raise ValueError('一次准备的帖子数量需在 1 到 30 条之间')

    existing = {item['trend_id'] for item in store.list_drafts()}
    candidates = [item for item in store.list_trends(
        category=args.category, sort='hot', limit=200
    ) if item['id'] not in existing]
    if len(candidates) < args.count:
        raise ValueError('当前可用的新热点数量不足，请先扫描数据源')

    results = []
    for trend in candidates[:args.count]:
        content = await llm.generate(
            trend, args.style, args.language, model=args.model, effort=args.effort,
        )
        draft = store.create_draft(trend, content, args.style, args.language)
        queued = store.queue_drafts([draft['id']])[0]
        results.append({'trend': trend['title'], 'draft_id': draft['id'],
                        'queue_id': queued['id'], 'content': content})
        output({'prepared': len(results), 'total': args.count, 'latest': results[-1]})


def main() -> None:
    args = build_parser().parse_args()
    store.initialize()

    if args.command == 'status':
        items = store.list_browser_queue()
        output({**store.statistics(), 'queue': {
            status: sum(item['status'] == status for item in items)
            for status in ('queued', 'opened', 'recorded', 'skipped')
        }})
    elif args.command == 'scan':
        output(asyncio.run(xsource.refresh_all()))
    elif args.command == 'hot':
        if args.count < 1 or args.count > 200:
            raise ValueError('条目数量需在 1 到 200 条之间')
        output(store.list_trends(category=args.category, limit=args.count))
    elif args.command == 'models':
        listing = asyncio.run(zen.catalog())
        output([model for model in listing['models']
                if args.search.casefold() in (model['name'] + ' ' + model['id']).casefold()])
    elif args.command == 'prepare':
        asyncio.run(prepare_posts(args))
    elif args.command == 'agent-run':
        output(agent_launch.submit(
            args.provider, args.connection, args.model,
            args.effort, args.mode, args.task, args.workdir, args.approve,
        ))
    elif args.command == 'agent-jobs':
        output(store.list_agent_jobs())
    elif args.command == 'creative-status':
        output(creative.status())
    elif args.command == 'creative-packs':
        output(store.creative_packs())
    elif args.command == 'creative-run':
        output(asyncio.run(creative.run_once(args.count, args.refresh)))
    elif args.command == 'enqueue':
        output(store.queue_drafts(args.draft_ids))
    elif args.command == 'queue':
        output(store.list_browser_queue())
    elif args.command == 'open-next':
        queue = store.list_browser_queue()
        pending = next((item for item in queue if item['status'] == 'queued'), None)
        if pending is None:
            raise ValueError('待发布队列中没有需要打开的草稿')
        url = browser_publish.compose_url(pending['content'])
        if not webbrowser.open(url, new=2):
            raise RuntimeError('系统浏览器无法打开 X 发帖编辑器')
        item = store.change_queue_status(pending['id'], 'open')
        output({'status': item['status'], 'queue_id': item['id'],
                'compose_url': url, 'notice': '请在浏览器中确认并点击发布'})
    elif args.command == 'record':
        url = browser_publish.validate_post_url(args.post_url)
        output(store.change_queue_status(args.queue_id, 'record', post_url=url))


if __name__ == '__main__':
    main()
