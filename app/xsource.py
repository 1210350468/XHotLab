import asyncio
import hashlib
import math
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx

from . import store

SEARCH_URL = 'https://x-lookup.mynameistito.com/search'
SOURCE_PREFIX = 'X 中文社区'
SEARCH_TOPICS = (
    ('x_zh_general', '热门讨论', '', 150),
    ('x_zh_ai', 'AI 与科技', '(AI OR 大模型 OR 科技)', 40),
    ('x_zh_games', '游戏与影视', '(游戏 OR 动漫 OR 电影)', 35),
    ('x_zh_life', '生活与趣事', '(生活 OR 吐槽 OR 搞笑)', 35),
    ('x_zh_digital', '数码与互联网', '(手机 OR 苹果 OR 软件 OR 开源)', 35),
)
POST_URL = re.compile(r'^https://(?:www\.)?x\.com/[A-Za-z0-9_]{1,15}/status/\d{10,20}/?$')
CHINESE = re.compile(r'[\u3400-\u9fff]')
PROMOTION = re.compile(
    r'抽奖|转发.{0,15}(?:抽|送|领)|关注.{0,15}(?:抽|送|领)|'
    r'空投|互粉|私信领取|领取.{0,12}(?:奖励|福利)|'
    r'推广链接|邀请码|返佣|进群领取|点赞.{0,12}关注'
)


def search_query(term: str, minimum_likes: int) -> str:
    since = (datetime.now(ZoneInfo('Asia/Shanghai')).date() - timedelta(days=1)).isoformat()
    return ' '.join(part for part in (
        term, 'lang:zh', f'min_faves:{minimum_likes}',
        f'since:{since}', '-filter:replies',
    ) if part)


def normalize_post(post: dict, category: str, label: str) -> dict | None:
    url = str(post.get('url') or '').replace('https://twitter.com/', 'https://x.com/').strip()
    text = str(post.get('text') or '').strip()
    if not POST_URL.fullmatch(url):
        return None
    if len(CHINESE.findall(text)) < 18 or len(text) < 45 or PROMOTION.search(text):
        return None
    if post.get('possibly_sensitive') is True:
        return None
    timestamp = post.get('created_timestamp')
    published = (datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
                 if timestamp is not None else parsedate_to_datetime(post['created_at']))
    if published.tzinfo is None:
        raise ValueError('X 原帖没有有效时区')
    age = (datetime.now(timezone.utc) - published).total_seconds() / 3600
    if not 0 <= age <= 30:
        return None
    author = post.get('author') or {}
    handle = str(author.get('screen_name') or '').strip()
    if not re.fullmatch(r'[A-Za-z0-9_]{1,15}', handle):
        return None
    likes = int(post.get('likes') or 0)
    shares = int(post.get('reposts') or post.get('retweets') or 0)
    comments = int(post.get('replies') or 0)
    views = int(post.get('views') or 0)
    if likes < 25:
        return None
    score = max(1, min(100, round(
        12 + 9 * math.log10(likes + 1)
        + 6 * math.log10(shares + 1)
        + 5 * math.log10(comments + 1)
        + 3 * math.log10(views + 1)
        - age * 0.50
    )))
    first = text.split('\n', maxsplit=1)[0].strip()
    if len(first) < 20:
        first = text[:90]
    title = first[:125]
    metrics = f'原帖作者 @{handle} · 点赞 {likes:,} · 转发 {shares:,} · 回复 {comments:,} · 浏览 {views:,}'
    summary = f'{metrics}\n原帖正文：{text[:850]}'
    return {
        'id': hashlib.sha256(('x-post|' + url).encode('utf-8')).hexdigest()[:28],
        'title': title,
        'summary': summary,
        'url': url,
        'source': f'{SOURCE_PREFIX} · {label}',
        'category': category,
        'published_at': published.astimezone(timezone.utc).isoformat(timespec='seconds'),
        'seen_at': store.now(),
        'volume': likes,
        'score': score,
    }


def extract_media(post: dict, trend_id: str) -> list[dict]:
    media = post.get('media') or {}
    entries = media.get('all') or []
    result = []
    for entry in entries[:12]:
        kind = entry.get('type')
        if kind not in ('photo', 'video', 'animated_gif'):
            continue
        original = str(entry.get('url') or '')
        preview = str(entry.get('thumbnail_url') or original)
        if not original.startswith('https://') or not preview.startswith('https://'):
            continue
        if urlsplit(preview).hostname != 'pbs.twimg.com':
            continue
        if urlsplit(original).hostname not in ('pbs.twimg.com', 'video.twimg.com'):
            continue
        result.append({
            'id': hashlib.sha256((trend_id + '|' + original).encode('utf-8')).hexdigest()[:32],
            'trend_id': trend_id,
            'kind': kind,
            'source_url': original,
            'preview_url': preview,
            'width': int(entry.get('width') or 0),
            'height': int(entry.get('height') or 0),
        })
    return result


async def query_topic(client: httpx.AsyncClient, topic: tuple) -> dict:
    category, label, term, minimum = topic
    response = await client.get(SEARCH_URL, params={
        'q': search_query(term, minimum), 'feed': 'top',
        'limit': 30, 'full': '1', 'format': 'json',
    })
    response.raise_for_status()
    payload = response.json()
    if payload.get('resource') != 'search' or not isinstance(payload.get('posts'), list):
        raise ValueError('X 中文搜索未返回有效帖子列表')
    items = []
    media = []
    for post in payload['posts']:
        item = normalize_post(post, category, label)
        if item is None:
            continue
        items.append(item)
        media.extend(extract_media(post, item['id']))
    await asyncio.to_thread(store.save_trends, items)
    await asyncio.to_thread(store.save_trend_media, media)
    await asyncio.to_thread(
        store.save_fetch_status, f'{SOURCE_PREFIX} · {label}', 'ok', len(items))
    return {'source': f'{SOURCE_PREFIX} · {label}', 'status': 'ok',
            'count': len(items), 'media': len(media)}


async def refresh_all() -> dict:
    async with httpx.AsyncClient(timeout=30, headers={'Accept': 'application/json'}) as client:
        results = await asyncio.gather(
            *(query_topic(client, topic) for topic in SEARCH_TOPICS),
            return_exceptions=True,
        )
    entries = []
    for topic, result in zip(SEARCH_TOPICS, results):
        if isinstance(result, BaseException):
            label = f'{SOURCE_PREFIX} · {topic[1]}'
            await asyncio.to_thread(
                store.save_fetch_status, label, 'error', 0,
                f'{type(result).__name__}: {result}'[:200])
            entries.append({'source': label, 'status': 'error', 'count': 0})
        else:
            entries.append(result)
    valid = sum(item['status'] == 'ok' for item in entries)
    if valid == 0:
        raise RuntimeError('X 中文帖子查询全部失败，请检查公开 X 搜索服务的连接状态')
    return {'sources': entries, 'ok': valid,
            'items': sum(item['count'] for item in entries)}
