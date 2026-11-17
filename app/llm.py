from . import store, zen


STYLES = {
    'opinion': '强观点：提出有根据、清晰、有讨论价值的个人观点。',
    'explain': '通俗科普：用最少文字讲清楚事情与读者的关系。',
    'humor': '轻松幽默：用准确、有分寸的幽默增加传播力。',
    'question': '讨论提问：以值得参与的具体问题收尾。',
    'reply': '热点评论：写一条适合加入公开讨论的简短、有信息量的独立看法。',
    'thread': '短串文：提供三条以内带编号的精炼分析，每条内容紧凑。',
}


async def generate_full(trend: dict, style: str = 'opinion', language: str = 'zh',
                        angle: str = '', model: str | None = None,
                        effort: str | None = None) -> dict:
    if style not in STYLES:
        raise ValueError('不支持的内容风格')
    if language not in ('en', 'zh'):
        raise ValueError('不支持的语言')

    settings = zen.settings()
    chosen = model or settings['compose_model']
    strength = effort or settings['compose_effort']
    context = store.profile()
    background = context['content'] if context['enabled'] else ''
    instructions = (
        'You are creating original Chinese-language X posts inspired by a popular X post. '
        'Use the original author and post as context; add a distinct, useful viewpoint. '
        'Do not copy the author’s words or claim their experiences as yours. '
        'Never invent events, quotes, figures, dates or personal experiences. '
        'Attribute unverified claims and avoid repetitive engagement bait. '
        'Write a natural post with a specific observation, not generic AI filler. '
        'Return only the publishable text. For a single post keep under 260 characters. '
        'For a thread use at most three numbered short posts, each under 260 characters.'
    )
    prompt = (
        f'Output language: {"English" if language == "en" else "Simplified Chinese"}\n'
        f'Writing style: {STYLES[style]}\n'
        f'Editorial direction: {angle[:280]}\n'
        f'Source: {trend["source"]}\n'
        f'Headline: {trend["title"]}\n'
        f'Summary: {trend["summary"][:700]}\n'
        f'Original X post URL: {trend["url"]}\n'
        f'Creator background (preferences only, not evidence of news): {background[:2800]}'
    )
    result = await zen.complete(
        [{'role': 'system', 'content': instructions},
         {'role': 'user', 'content': prompt}],
        model_id=chosen, effort=strength, max_tokens=600,
    )
    store.save_usage(result['model'], 'rewrite', result['usage'])
    return result


async def generate(trend: dict, style: str = 'opinion', language: str = 'zh',
                   angle: str = '', model: str | None = None,
                   effort: str | None = None) -> str:
    result = await generate_full(trend, style, language, angle, model, effort)
    return result['text']


async def check_connection() -> dict:
    return await zen.check_connection()
