import httpx


BASE = 'http://127.0.0.1:8766'


def main():
    with httpx.Client(base_url=BASE, timeout=20) as client:
        response = client.get('/api/health')
        response.raise_for_status()
        assert response.json()['ok'] is True

        response = client.get('/')
        response.raise_for_status()
        assert 'XHotLab' in response.text
        for asset in ('/assets/app.js', '/assets/styles.css'):
            response = client.get(asset)
            response.raise_for_status()
            assert response.text

        response = client.get('/api/overview')
        response.raise_for_status()
        overview = response.json()
        assert overview['total'] > 0
        assert overview['freshness_window_hours'] == 24
        assert overview['scan_interval_minutes'] >= 5
        assert overview['last_checked']
        assert all(item['source'].startswith('X 中文社区') for item in overview['sources'])
        assert len(overview['sources']) == 5
        assert any(item['status'] == 'ok' for item in overview['sources'])

        response = client.get('/api/queue')
        response.raise_for_status()
        assert isinstance(response.json(), list)

        response = client.get('/api/trends', params={'category': 'x_zh_ai', 'limit': 1})
        response.raise_for_status()
        trends = response.json()
        assert trends
        trend = trends[0]
        assert trend['title'] and trend['url'].startswith('https://x.com/')

        response = client.get('/api/trends', params={'category': 'cn_trending'})
        response.raise_for_status()
        assert response.json() == []

        draft_id = None
        queue_id = None
        try:
            response = client.post('/api/drafts', json={
                'trend_id': trend['id'],
                'language': 'zh',
                'content': f'正在研究热点：{trend["title"]}。',
            })
            response.raise_for_status()
            draft_id = response.json()['id']

            response = client.put(f'/api/drafts/{draft_id}', json={
                'content': f'已记录公开趋势：{trend["title"]}。'
            })
            response.raise_for_status()

            response = client.get('/api/drafts')
            response.raise_for_status()
            assert any(d['id'] == draft_id and d['content'].startswith('已记录') for d in response.json())

            response = client.post('/api/queue', json={'draft_ids': [draft_id]})
            response.raise_for_status()
            queue_id = response.json()[0]['id']

            response = client.post('/api/queue', json={'draft_ids': [draft_id]})
            response.raise_for_status()
            assert response.json()[0]['id'] == queue_id

            response = client.post(f'/api/queue/{queue_id}/open')
            response.raise_for_status()
            opened = response.json()
            assert opened['item']['status'] == 'opened'
            assert opened['compose_url'].startswith('https://x.com/intent/post?text=')
            assert 'status=' not in opened['compose_url']

            response = client.post(f'/api/queue/{queue_id}/record', json={'post_url': 'http://localhost/'})
            assert response.status_code == 422

            response = client.post(f'/api/queue/{queue_id}/requeue')
            response.raise_for_status()
            assert response.json()['status'] == 'queued'

            response = client.post(f'/api/queue/{queue_id}/skip')
            response.raise_for_status()
            assert response.json()['status'] == 'skipped'

            response = client.post('/api/queue', json={'draft_ids': [draft_id]})
            response.raise_for_status()
            assert response.json()[0]['status'] == 'queued'
        finally:
            if queue_id:
                response = client.delete(f'/api/queue/{queue_id}')
                response.raise_for_status()
            if draft_id:
                response = client.delete(f'/api/drafts/{draft_id}')
                response.raise_for_status()

        print(f'Live smoke test passed: {overview["total"]} authentic X Chinese posts, '
              f'{len(overview["sources"])} X search categories, draft and queue operations verified.')


if __name__ == '__main__':
    main()
