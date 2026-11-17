from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import httpx
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:8766'
ACTION = {'X-XHotLab-Action': '1'}


def main():
    with httpx.Client(base_url=BASE, timeout=50) as client:
        pack = client.get('/api/creative/packs').json()[0]
        trend_id = pack['trend_id']
        post = client.get('/api/trends/' + trend_id)
        post.raise_for_status()
        original = post.json()
        source_text = original['summary'].split('原帖正文：')[-1]
        assert source_text

        captured = client.post('/api/extension/capture', headers=ACTION, json={
            'url': original['url'],
            'text': source_text,
            'published_at': original['published_at'],
            'likes': original['volume'],
            'media': [],
        })
        captured.raise_for_status()
        assert captured.json()['trend']['id'] == trend_id
        assert client.post('/api/extension/capture', json={
            'url': original['url'], 'text': source_text,
        }).status_code == 403

        filename = ROOT / 'data' / 'generated' / pack['image_directory'] / 'cover.png'
        image_data = filename.read_bytes()
        draft_id = None
        queue_id = None
        try:
            response = client.post('/api/drafts', json={
                'trend_id': trend_id,
                'language': 'zh',
                'content': pack['content'],
            })
            response.raise_for_status()
            draft_id = response.json()['id']

            response = client.post('/api/queue', json={'draft_ids': [draft_id]})
            response.raise_for_status()
            queue_id = response.json()[0]['id']

            response = client.post('/api/queue/' + queue_id + '/media/upload',
                                   headers=ACTION, files={
                                       'files': ('cover.png', image_data, 'image/png'),
                                   })
            response.raise_for_status()
            body = response.json()
            assert body['uploaded'] == 1
            uploaded = [entry for entry in body['attachments']
                        if entry['origin'] == 'user']
            assert len(uploaded) == 1
            assert uploaded[0]['ready'] and uploaded[0]['selected']
            resource = client.get(uploaded[0]['url'])
            resource.raise_for_status()
            with Image.open(BytesIO(resource.content)) as picture:
                assert picture.format == 'PNG'
                assert picture.size == (900, 1200)

            response = client.get('/api/queue/' + queue_id + '/bundle')
            response.raise_for_status()
            with ZipFile(BytesIO(response.content)) as bundle:
                image_path = next(name for name in bundle.namelist()
                                  if name.startswith('attachments/'))
                assert bundle.read(image_path) == image_data
                assert pack['content'].encode('utf-8') in bundle.read('post.txt')

            response = client.put('/api/queue/' + queue_id + '/media',
                                  headers=ACTION, json={'media_ids': []})
            response.raise_for_status()
            assert not any(entry['selected'] for entry in response.json())
            response = client.put('/api/queue/' + queue_id + '/media',
                                  headers=ACTION,
                                  json={'media_ids': [uploaded[0]['id']]})
            response.raise_for_status()
            assert sum(entry['selected'] for entry in response.json()) == 1
        finally:
            if queue_id:
                response = client.delete('/api/queue/' + queue_id)
                response.raise_for_status()
                assert not (ROOT / 'data' / 'user_media' / queue_id).exists()
            if draft_id:
                response = client.delete('/api/drafts/' + draft_id)
                response.raise_for_status()

    print('Real Edge upload flow passed: X post capture, PNG upload, '
          'server-side validation, image selection, ZIP publishing bundle and cleanup.')


if __name__ == '__main__':
    main()
