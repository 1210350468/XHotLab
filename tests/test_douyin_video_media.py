from pathlib import Path

import pytest

from app import douyin_pipeline, media, store


VIDEO = Path(__file__).resolve().parents[1].parent / 'ArenaForge' / 'Artifacts' / 'skill-demo' / 'FurnaceHorizon.mp4'


def create_candidate(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'DB_FILE', tmp_path / 'xhotlab.sqlite3')
    monkeypatch.setattr(media, 'SOURCE_VIDEO', tmp_path / 'source_videos')
    store.initialize()

    candidate_id = 'douyin:1234567890123456'
    source_url = 'https://www.douyin.com/video/1234567890123456'
    trend = {
        'id': candidate_id,
        'title': '机器人实测',
        'summary': '原视频来源记录',
        'url': source_url,
        'source': '抖音 · CreatorHub 实际采集',
        'category': 'douyin_video',
        'published_at': '2026-11-16T08:00:00+00:00',
        'seen_at': '2026-11-16T08:00:00+00:00',
        'volume': 1200,
        'score': 80,
    }
    store.save_trends([trend])
    draft = store.create_draft(
        trend, '机器人实测的原创点评', 'douyin_video_comment', 'zh')
    queue = store.queue_drafts([draft['id']])[0]
    store.upsert_douyin_candidates([{
        'id': candidate_id,
        'job_id': 1,
        'content_id': 10,
        'source_url': source_url,
        'description': '机器人实测',
        'author_name': '测试作者',
        'like_count': 1200,
        'comment_count': 30,
        'published_at': '2026-11-16T08:00:00+00:00',
        'cover_url': 'https://p3-pc-sign.douyinpic.com/cover.jpg',
    }])
    store.schedule_douyin_candidate(
        candidate_id, queue['id'], '2026-11-16T12:30:00+08:00')
    return candidate_id, queue['id']


def test_legacy_authorization_columns_are_removed_on_initialize(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'DB_FILE', tmp_path / 'xhotlab.sqlite3')
    store.initialize()
    with store.connection() as db:
        db.execute("""ALTER TABLE douyin_video_candidates
            ADD COLUMN rights_status TEXT NOT NULL DEFAULT 'unverified'""")
        db.execute("""ALTER TABLE douyin_video_candidates
            ADD COLUMN rights_evidence TEXT NOT NULL DEFAULT ''""")

    store.initialize()

    with store.connection() as db:
        columns = {
            row['name'] for row in db.execute(
                'PRAGMA table_info(douyin_video_candidates)')
        }
    assert 'rights_status' not in columns
    assert 'rights_evidence' not in columns


def test_douyin_video_import_needs_no_extra_authorization_record(tmp_path, monkeypatch):
    candidate_id, _queue_id = create_candidate(tmp_path, monkeypatch)

    imported = media.import_douyin_video(candidate_id, str(VIDEO))

    assert Path(imported['path']).is_file()
    assert 'rights_status' not in store.get_douyin_candidate(candidate_id)


def test_douyin_video_import_attaches_real_mp4_to_publish_queue(tmp_path, monkeypatch):
    candidate_id, queue_id = create_candidate(tmp_path, monkeypatch)

    imported = media.import_douyin_video(candidate_id, str(VIDEO))

    target = Path(imported['path'])
    assert target.is_file()
    assert target.read_bytes() == VIDEO.read_bytes()
    assert imported['candidate_id'] == candidate_id
    assert imported['attachments'][0]['id'] == candidate_id
    assert imported['attachments'][0]['kind'] == 'video'
    assert imported['attachments'][0]['selected']
    assert media.selected_media_files(queue_id) == [target]
    assert store.get_douyin_candidate(candidate_id)['video_file'] == imported['video_file']


def test_douyin_pipeline_reuses_an_existing_local_video(tmp_path, monkeypatch):
    candidate_id, queue_id = create_candidate(tmp_path, monkeypatch)
    media.import_douyin_video(candidate_id, str(VIDEO))

    result = douyin_pipeline.download_candidate(candidate_id)

    assert result['reused']
    assert result['candidate']['video_file']
    assert result['attachments'][0]['selected']
    assert media.selected_media_files(queue_id)[0].is_file()


def test_user_mp4_upload_needs_no_extra_authorization_record(tmp_path, monkeypatch):
    candidate_id, queue_id = create_candidate(tmp_path, monkeypatch)

    with VIDEO.open('rb') as source:
        uploaded = media.save_user_video(queue_id, VIDEO.name, source)

    assert uploaded['filename'] == VIDEO.name
    assert uploaded['cached_file'].endswith('.mp4')
    assert media.media_choices(queue_id)[0]['kind'] == 'video'


def test_douyin_video_path_rejects_files_outside_source_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(media, 'SOURCE_VIDEO', tmp_path / 'source_videos')

    with pytest.raises(ValueError, match='超出素材目录'):
        media.source_video_path('../outside.mp4')


def test_manual_douyin_caption_is_preserved_without_author_or_source():
    candidate_id = 'douyin:1234567890123456'
    caption = '给这段视频写一句自己的标题 #有意思'

    assert douyin_pipeline.manual_caption(candidate_id, {candidate_id: caption}) == caption
    assert douyin_pipeline.manual_caption(candidate_id, {
        candidate_id: '  ' + caption + '  '
    }) == caption


def test_manual_douyin_caption_is_required():
    candidate_id = 'douyin:1234567890123456'

    with pytest.raises(ValueError, match='手动填写'):
        douyin_pipeline.manual_caption(candidate_id, {})
    with pytest.raises(ValueError, match='1 到 280'):
        douyin_pipeline.manual_caption(candidate_id, {candidate_id: '   '})
    with pytest.raises(ValueError, match='1 到 280'):
        douyin_pipeline.manual_caption(candidate_id, {candidate_id: '文' * 281})
