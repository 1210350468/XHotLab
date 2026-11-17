import asyncio
import re
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from . import creatorhub_bridge, media, store


LOCAL_TIME = ZoneInfo('Asia/Shanghai')
PUBLIC_VIDEO = re.compile(r'https://www\.douyin\.com/video/(\d{12,22})')
NEXT_SLOTS = (time(12, 30), time(19, 0))


def synchronize(job_id: int) -> dict:
    if not creatorhub_bridge.running():
        raise ValueError('请启动 CreatorHub 后再读取抖音采集结果')
    with creatorhub_bridge._client(timeout=18) as client:
        job_response = client.get(f'/api/collections/{job_id}')
        job_response.raise_for_status()
        job = job_response.json()
        if job['platform'] != 'douyin':
            raise ValueError('当前任务必须来自抖音视频采集')
        if job['content_type'] != 'video':
            raise ValueError('请使用视频类型的抖音采集任务')
        collected = []
        page = 1
        while True:
            response = client.get(f'/api/collections/{job_id}/contents',
                                  params={'page': page, 'page_size': 100})
            response.raise_for_status()
            result = response.json()
            collected.extend(result['items'])
            if page >= result['pages']:
                break
            page += 1
    records = []
    for source in collected:
        if source['platform'] != 'douyin' or source['media_type'] != 'video':
            continue
        video_url = source['url']
        matched = PUBLIC_VIDEO.fullmatch(video_url)
        if not matched:
            raise ValueError('CreatorHub 返回了不合法的抖音原视频链接')
        if source['like_count'] < 1000:
            continue
        records.append({
            'id': 'douyin:' + matched[1],
            'job_id': job_id,
            'content_id': source['id'],
            'source_url': video_url,
            'description': source['desc'],
            'author_name': source['author_name'],
            'like_count': source['like_count'],
            'comment_count': source['comment_count'],
            'published_at': datetime.fromtimestamp(
                source['create_time'], timezone.utc
            ).isoformat(timespec='seconds'),
            'cover_url': source['cover_url'],
        })
    store.upsert_douyin_candidates(records)
    return {'job_id': job_id, 'job_status': job['status'],
            'discovered': len(records),
            'error': job.get('error') or '',
            'candidates': store.douyin_candidates()}


def synchronize_all() -> dict:
    if not creatorhub_bridge.running():
        raise ValueError('CreatorHub 服务未启动')
    with creatorhub_bridge._client(timeout=15) as client:
        response = client.get('/api/collections',
                              params={'platform': 'douyin', 'limit': 20})
        response.raise_for_status()
        jobs = response.json()
    matching = [
        entry for entry in jobs
        if entry['platform'] == 'douyin' and
        entry.get('content_type') == 'video'
    ]
    results = [synchronize(entry['id']) for entry in matching]
    return {
        'jobs': len(results),
        'discovered': sum(value['discovered'] for value in results),
        'candidates': store.douyin_candidates(),
        'job_results': [{
            'id': item['job_id'],
            'status': item['job_status'],
            'error': item['error'],
        } for item in results],
    }


async def refresh_existing_jobs() -> None:
    if await asyncio.to_thread(creatorhub_bridge.running):
        await asyncio.to_thread(synchronize_all)


def download_candidate(candidate_id: str) -> dict:
    candidate = store.get_douyin_candidate(candidate_id)
    if candidate is None:
        raise LookupError('抖音候选视频不存在')
    if not candidate['queue_id']:
        raise ValueError('请先将抖音视频加入 X 发布安排')

    if candidate['video_file']:
        existing = media.source_video_path(candidate['video_file'])
        if existing.is_file():
            attachments = media.select_queue_media(
                candidate['queue_id'], [candidate_id])
            return {
                'candidate': store.get_douyin_candidate(candidate_id),
                'video_file': candidate['video_file'],
                'path': str(existing),
                'size': existing.stat().st_size,
                'attachments': attachments,
                'reused': True,
            }

    if not creatorhub_bridge.running():
        raise ValueError('CreatorHub 服务尚未启动')

    with creatorhub_bridge._client(timeout=18) as client:
        response = client.get(f"/api/collections/{candidate['job_id']}")
        response.raise_for_status()
        job = response.json()
        source = None
        page = 1
        while True:
            response = client.get(
                f"/api/collections/{candidate['job_id']}/contents",
                params={'page': page, 'page_size': 100},
            )
            response.raise_for_status()
            contents = response.json()
            source = next((item for item in contents['items']
                           if int(item['id']) == int(candidate['content_id'])), None)
            if source is not None or page >= contents['pages']:
                break
            page += 1
    if job.get('platform') != 'douyin':
        raise ValueError('候选视频对应的 CreatorHub 任务属于其他平台')

    local_path = str((source or {}).get('local_path') or '').strip()
    if local_path:
        local_video = Path(local_path).expanduser()
        if not local_video.is_absolute():
            local_video = creatorhub_bridge.CREATORHUB_ROOT / local_video
        if local_video.is_file() and local_video.suffix.lower() == '.mp4':
            imported = media.import_douyin_video(
                candidate_id, str(local_video.resolve(strict=True)))
            return {
                'candidate': store.get_douyin_candidate(candidate_id),
                **imported,
                'reused': True,
            }

    account_id = job.get('account_id')
    if not account_id:
        raise ValueError('CreatorHub 采集任务没有关联抖音登录账号')

    result = creatorhub_bridge.share(
        candidate['source_url'], True, int(account_id))
    items = result.get('results') or []
    item = next((entry for entry in items if entry.get('ok')), None)
    if not result.get('ok') or item is None:
        detail = next((entry.get('error') for entry in items
                       if entry.get('error')), 'CreatorHub 没有返回成功的视频下载结果')
        raise ValueError(detail)
    videos = [entry for entry in item.get('files', [])
              if entry.get('role') == 'media'
              and Path(str(entry.get('path') or '')).suffix.lower() == '.mp4']
    if not videos:
        raise ValueError('CreatorHub 下载结果中没有 MP4 视频文件')

    imported = media.import_douyin_video(candidate_id, videos[0]['path'])
    return {
        'candidate': store.get_douyin_candidate(candidate_id),
        **imported,
        'reused': False,
    }


def upcoming_slots(count: int) -> list[datetime]:
    now = datetime.now(LOCAL_TIME) + timedelta(minutes=35)
    slots = []
    for offset in range(15):
        day = (now + timedelta(days=offset)).date()
        for hour in NEXT_SLOTS:
            scheduled = datetime.combine(day, hour, tzinfo=LOCAL_TIME)
            if scheduled > now:
                slots.append(scheduled)
    reserved = {
        item['scheduled_at'] for item in store.douyin_candidates()
        if item['scheduled_at']
    }
    return [slot for slot in slots if slot.astimezone(timezone.utc).isoformat(
        timespec='seconds') not in reserved][:count]


def manual_caption(candidate_id: str, captions: dict[str, str] | None) -> str:
    caption = (captions or {}).get(candidate_id)
    if caption is None:
        raise ValueError('请手动填写这条视频的 X 发布文案')
    content = caption.strip()
    if not content or len(content) > 280:
        raise ValueError('发布文案长度必须在 1 到 280 个字符之间')
    return content


async def arrange(count: int = 3,
                  captions: dict[str, str] | None = None,
                  candidate_id: str | None = None) -> dict:
    if count < 1 or count > 5:
        raise ValueError('单次可安排 1 至 5 条视频选题')
    if candidate_id:
        candidate = store.get_douyin_candidate(candidate_id)
        if candidate is None:
            raise ValueError('选中的抖音视频不存在，请重新读取热门列表')
        if candidate['queue_id']:
            raise ValueError('这条视频已加入发布队列，请直接继续编辑')
        candidate_rows = [candidate]
    else:
        candidate_rows = [
            item for item in store.douyin_candidates()
            if not item['queue_id']
        ][:count]
    captions_by_id = {
        candidate['id']: manual_caption(candidate['id'], captions)
        for candidate in candidate_rows
    }
    slots = upcoming_slots(len(candidate_rows))
    if len(slots) != len(candidate_rows):
        raise ValueError('当前没有可用的发布时间安排')
    scheduled = []
    for candidate, slot in zip(candidate_rows, slots):
        caption = captions_by_id[candidate['id']]
        trend = {
            'id': candidate['id'],
            'title': candidate['description'][:120],
            'summary': ('抖音原视频：' + candidate['description'][:650] +
                        '\n作者：' + candidate['author_name'] +
                        '\n点赞：' + str(candidate['like_count'])),
            'url': candidate['source_url'],
            'source': '抖音 · CreatorHub 实际采集',
            'category': 'douyin_video',
            'published_at': candidate['published_at'],
            'seen_at': store.now(),
            'volume': candidate['like_count'],
            'score': min(100, 25 + candidate['like_count'] // 250),
        }
        store.save_trends([trend])
        draft = store.create_draft(trend, caption, 'manual', 'zh')
        item = store.queue_drafts([draft['id']])[0]
        planned = store.schedule_douyin_candidate(
            candidate['id'], item['id'],
            slot.astimezone(timezone.utc).isoformat(timespec='seconds'),
        )
        scheduled.append({
            'candidate_id': candidate['id'],
            'queue_id': item['id'],
            'scheduled_at': planned['scheduled_at'],
            'caption': caption,
            'source_url': candidate['source_url'],
            'author_name': candidate['author_name'],
        })
    return {'arranged': len(scheduled), 'posts': scheduled}
