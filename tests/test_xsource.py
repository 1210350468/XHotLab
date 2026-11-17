import asyncio
from datetime import datetime, timezone

import httpx

from app import store, xsource


def test_real_x_chinese_search_returns_authentic_posts():
    category, label, term, minimum = xsource.SEARCH_TOPICS[1]
    query = xsource.search_query(term, minimum)
    with httpx.Client(timeout=25) as client:
        response = client.get(xsource.SEARCH_URL, params={
            'q': query, 'feed': 'top', 'limit': 30, 'format': 'json', 'full': '1',
        })
        response.raise_for_status()
        payload = response.json()
    assert payload['resource'] == 'search'
    assert payload['posts']
    valid = [item for post in payload['posts']
             if (item := xsource.normalize_post(post, category, label))]
    assert valid
    assert all(item['url'].startswith('https://x.com/') for item in valid)
    assert all('原帖作者 @' in item['summary'] for item in valid)
    assert all(item['volume'] >= 25 for item in valid)


def test_x_source_search_query_preserves_actual_language_and_recency():
    query = xsource.search_query('游戏 OR 电影', 80)
    assert 'lang:zh' in query
    assert 'min_faves:80' in query
    assert '-filter:replies' in query
    assert 'since:' in query


def test_saved_x_data_only():
    store.initialize()
    visible = store.list_trends(limit=200)
    assert visible
    assert all(item['category'].startswith('x_zh') for item in visible)
    assert all(item['url'].startswith('https://x.com/') for item in visible)
    assert all(source['source'].startswith('X 中文社区') for source in store.fetch_logs())


def test_real_freshness_sort_and_recent_counts():
    store.initialize()
    now = datetime.now(timezone.utc)
    posts = store.list_trends(limit=200)
    assert posts
    assert all(0 <= (now - datetime.fromisoformat(item['published_at'])).total_seconds()
               <= 24 * 3600 + 10 for item in posts)
    assert all(0 < item['fresh_score'] <= item['score'] for item in posts)
    assert all(posts[i]['fresh_score'] >= posts[i + 1]['fresh_score']
               for i in range(len(posts) - 1))
    newest = store.list_trends(sort='new', limit=200)
    assert all(newest[i]['published_at'] >= newest[i + 1]['published_at']
               for i in range(len(newest) - 1))
    stats = store.statistics()
    assert stats['freshness_window_hours'] == 24
    assert stats['total'] == sum(group['count'] for group in stats['categories'])
    assert len(posts) == min(stats['total'], 200)
