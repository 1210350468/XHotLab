import httpx


BASE = 'http://127.0.0.1:8766'


def main():
    with httpx.Client(base_url=BASE, timeout=25) as client:
        listing = client.get('/api/zen/models')
        listing.raise_for_status()
        models = listing.json()
        assert models['total'] >= 50

        settings_response = client.get('/api/zen/settings')
        settings_response.raise_for_status()
        settings = settings_response.json()
        assert settings['compose_model'] in {model['id'] for model in models['models']}
        assert isinstance(settings['key_configured'], bool)
        assert 'api_key' not in settings

        response = client.put('/api/zen/settings', headers={'X-XHotLab-Action': '1'}, json={
            'plan': 'payg',
            'chat_model': settings['chat_model'],
            'compose_model': 'invalid-model-id',
            'chat_effort': settings['chat_effort'],
            'compose_effort': settings['compose_effort'],
        })
        assert response.status_code == 422
        assert client.get('/api/zen/settings').json()['compose_model'] == settings['compose_model']

        response = client.get('/api/agents/availability')
        response.raise_for_status()
        assert response.json()['installed']['codex']
        assert response.json()['installed']['claude']

        response = client.post('/api/agents/jobs', headers={'X-XHotLab-Action': '1'}, json={
            'provider': 'codex', 'connection': 'native', 'mode': 'read-only',
            'workdir': 'D:\\coding\\XHotLab',
            'task': 'Inspect documentation', 'approved': False,
        })
        assert response.status_code == 422

        response = client.post('/api/chats', json={})
        response.raise_for_status()
        chat_id = response.json()['id']
        try:
            response = client.get('/api/chats/' + chat_id)
            response.raise_for_status()
            assert response.json()['messages'] == []
            if not settings['key_configured']:
                response = client.post('/api/chats/' + chat_id + '/send', json={
                    'text': 'Hello', 'model': settings['chat_model'], 'effort': settings['chat_effort'],
                })
                assert response.status_code == 409
        finally:
            response = client.delete('/api/chats/' + chat_id,
                                     headers={'X-XHotLab-Action':'1'})
            response.raise_for_status()

        response = client.get('/api/zen/usage')
        response.raise_for_status()
        assert 'total_cost_usd' in response.json()

        response = client.get('/assets/assistant.js')
        response.raise_for_status()
        assert 'showAgentWorkspace' in response.text

    print(f'Real Zen API HTTP smoke passed: {models["total"]} models, '
          'profile/chat persistence, model validation and Agent permission checks.')


if __name__ == '__main__':
    main()
