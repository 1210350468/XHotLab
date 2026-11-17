from io import BytesIO
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
from urllib.parse import quote, urlsplit
from uuid import uuid4

import httpx
from PIL import Image

from . import store
from .config import ROOT

SOURCE_MEDIA = ROOT / 'data' / 'source_media'
GENERATED_MEDIA = ROOT / 'data' / 'generated'
USER_MEDIA = ROOT / 'data' / 'user_media'
SOURCE_VIDEO = ROOT / 'data' / 'source_videos'
MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_VIDEO_BYTES = 512 * 1024 * 1024
MAX_SELECTED_MEDIA = 4
GENERATED_NAMES = ('cover', 'context', 'discussion')
FILE_EXTENSIONS = {'JPEG': '.jpg', 'PNG': '.png', 'WEBP': '.webp', 'GIF': '.gif'}


def validated_preview(url: str) -> str:
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname != 'pbs.twimg.com'
            or parsed.username or parsed.password or parsed.port):
        raise ValueError('X 原帖图片必须位于 pbs.twimg.com')
    return url


def source_video_path(relative_file: str, *, strict: bool = False) -> Path:
    relative = Path(relative_file)
    if relative.is_absolute() or not relative.parts:
        raise ValueError('抖音视频文件路径无效')
    root = SOURCE_VIDEO.resolve()
    target = (root / relative).resolve(strict=strict)
    if target == root or root not in target.parents:
        raise ValueError('抖音视频文件路径超出素材目录')
    return target


async def import_source_media(trend_id: str) -> list[dict]:
    if store.get_trend(trend_id) is None:
        raise LookupError('未找到 X 原帖')
    entries = store.trend_media(trend_id)
    source_dir = SOURCE_MEDIA / trend_id
    imported = []
    async with httpx.AsyncClient(timeout=35, follow_redirects=False) as client:
        for entry in entries[:8]:
            validated_preview(entry['preview_url'])
            if entry['cached_file']:
                filename = SOURCE_MEDIA / entry['cached_file']
                if not filename.is_file():
                    raise FileNotFoundError(f'已登记的 X 原帖图片文件不存在：{filename}')
                imported.append(entry)
                continue

            async with client.stream('GET', entry['preview_url']) as response:
                response.raise_for_status()
                media_type = response.headers.get('content-type', '').split(';')[0].strip()
                if not media_type.startswith('image/'):
                    raise ValueError('原帖媒体地址返回了非图片内容')
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_IMAGE_BYTES:
                        raise ValueError('原帖图片超过 12 MiB 的单文件限制')
            with Image.open(BytesIO(data)) as picture:
                if picture.format not in FILE_EXTENSIONS:
                    raise ValueError('X 原帖图片格式不支持')
                if picture.width * picture.height > 45_000_000:
                    raise ValueError('原帖图片像素数量过大')
                format_name = picture.format
                picture.verify()
            source_dir.mkdir(parents=True, exist_ok=True)
            path = source_dir / (entry['id'] + FILE_EXTENSIONS[format_name])
            path.write_bytes(data)
            relative_path = path.relative_to(SOURCE_MEDIA).as_posix()
            store.update_cached_media(entry['id'], relative_path)
            entry['cached_file'] = relative_path
            imported.append(entry)
    return imported


def media_choices(queue_id: str) -> list[dict]:
    item = store.queue_media_info(queue_id)
    if item is None:
        raise LookupError('待发布内容不存在')
    selected = set(store.queue_media_ids(queue_id))
    choices = []

    if item['image_directory']:
        directory = GENERATED_MEDIA / item['image_directory']
        for name in GENERATED_NAMES:
            filename = directory / (name + '.png')
            if filename.is_file():
                choices.append({
                    'id': 'generated:' + name,
                    'origin': 'generated',
                    'kind': 'photo',
                    'label': {'cover': '原创封面', 'context': '原创内容说明',
                              'discussion': '原创互动图卡'}[name],
                    'url': '/generated/' + item['image_directory'] + '/' + name + '.png',
                    'ready': True, 'selected': 'generated:' + name in selected,
                })

    for original in store.trend_media(item['trend_id']):
        photo_path = original['cached_file']
        cached = bool(photo_path and (SOURCE_MEDIA / photo_path).is_file())
        choices.append({
            'id': original['id'],
            'origin': 'source',
            'kind': 'photo',
            'label': {'photo': '原帖图片', 'video': '原帖视频封面',
                      'animated_gif': '原帖动图预览'}[original['kind']],
            'url': ('/source-media/' + photo_path) if cached else validated_preview(original['preview_url']),
            'ready': cached, 'selected': original['id'] in selected,
            'source_url': item['trend_id'],
        })
    candidate = store.get_douyin_candidate(item['trend_id'])
    if candidate and candidate['video_file']:
        relative_file = candidate['video_file']
        filename = source_video_path(relative_file)
        choices.append({
            'id': candidate['id'], 'origin': 'douyin', 'kind': 'video',
            'label': '抖音原视频 · ' + candidate['author_name'],
            'url': '/source-videos/' + quote(relative_file, safe='/'),
            'ready': filename.is_file(),
            'selected': candidate['id'] in selected,
            'source_url': candidate['source_url'],
        })
    for uploaded in store.uploaded_media(queue_id):
        path = USER_MEDIA / uploaded['cached_file']
        is_video = path.suffix.lower() == '.mp4'
        choices.append({
            'id': uploaded['id'], 'origin': 'user',
            'kind': 'video' if is_video else 'photo',
            'label': uploaded['filename'],
            'url': '/user-media/' + uploaded['cached_file'],
            'ready': path.is_file(), 'selected': uploaded['id'] in selected,
        })
    return choices


def save_user_image(queue_id: str, filename: str, data: bytes) -> dict:
    item = store.queue_media_info(queue_id)
    if item is None:
        raise LookupError('待发布内容不存在')
    if item['status'] not in ('queued', 'opened'):
        raise ValueError('已完成的发布记录禁止上传新图片')
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError('图片大小需要在 1 字节到 12 MiB 之间')
    with Image.open(BytesIO(data)) as picture:
        if picture.format not in FILE_EXTENSIONS:
            raise ValueError('仅支持 JPEG、PNG、WEBP 和 GIF 图片')
        if picture.width * picture.height > 45_000_000:
            raise ValueError('图片像素数量过大')
        extension = FILE_EXTENSIONS[picture.format]
        picture.verify()
    unique_name = str(uuid4()) + extension
    directory = USER_MEDIA / queue_id
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / unique_name
    target.write_bytes(data)
    return store.add_uploaded_media(queue_id, Path(filename).name,
                                    target.relative_to(USER_MEDIA).as_posix())


def save_user_video(queue_id: str, filename: str, source) -> dict:
    item = store.queue_media_info(queue_id)
    if item is None:
        raise LookupError('待发布任务不存在')
    if item['status'] not in ('queued', 'opened'):
        raise ValueError('已经完成的任务无法上传视频')
    if Path(filename).suffix.lower() != '.mp4':
        raise ValueError('X 视频上传仅接受 MP4 容器')
    source.seek(0, os.SEEK_END)
    length = source.tell()
    source.seek(0)
    if length < 1 or length > MAX_VIDEO_BYTES:
        raise ValueError('视频大小需要在 1 字节到 512 MiB 之间')
    directory = USER_MEDIA / queue_id
    directory.mkdir(parents=True, exist_ok=True)
    filename_on_disk = str(uuid4()) + '.mp4'
    with tempfile.TemporaryDirectory(prefix='video-validation-', dir=directory) as temporary:
        inspected = Path(temporary) / filename_on_disk
        with inspected.open('wb') as output:
            shutil.copyfileobj(source, output, length=1024 * 1024)
        validate_mp4_file(inspected)
        inspected.rename(directory / filename_on_disk)
    return store.add_uploaded_media(
        queue_id, Path(filename).name,
        (Path(queue_id) / filename_on_disk).as_posix(),
    )


def import_douyin_video(candidate_id: str, source_path: str) -> dict:
    candidate = store.get_douyin_candidate(candidate_id)
    if candidate is None:
        raise LookupError('抖音候选视频不存在')
    queue_id = candidate['queue_id']
    if not queue_id:
        raise ValueError('请先将抖音视频加入 X 发布安排')
    queue = store.queue_media_info(queue_id)
    if queue is None:
        raise LookupError('抖音视频对应的发布任务不存在')
    if queue['status'] not in ('queued', 'opened'):
        raise ValueError('当前发布任务已经结束，无法添加视频附件')

    source = Path(source_path).expanduser().resolve(strict=True)
    if not source.is_file() or source.suffix.lower() != '.mp4':
        raise ValueError('CreatorHub 下载结果需要是 MP4 视频文件')
    if not 0 < source.stat().st_size <= MAX_VIDEO_BYTES:
        raise ValueError('抖音视频大小需要在 1 字节到 512 MiB 之间')
    validate_mp4_file(source)

    SOURCE_VIDEO.mkdir(parents=True, exist_ok=True)
    relative_file = (
        str(candidate['content_id']) + '_' +
        candidate_id.split(':', 1)[-1] + '.mp4'
    )
    target = source_video_path(relative_file)
    if source != target:
        shutil.copyfile(source, target)
    validate_mp4_file(target)
    store.set_douyin_video_file(candidate_id, relative_file)
    attachments = select_queue_media(queue_id, [candidate_id])
    return {
        'candidate_id': candidate_id,
        'video_file': relative_file,
        'path': str(target),
        'size': target.stat().st_size,
        'attachments': attachments,
    }


def validate_mp4_file(filename: Path) -> dict:
    ffprobe = shutil.which('ffprobe')
    if not ffprobe:
        raise FileNotFoundError('系统缺少 FFprobe 视频校验工具')
    metadata = json.loads(subprocess.run([
        ffprobe, '-v', 'error', '-show_entries',
        'format=duration:stream=codec_type,codec_name,width,height',
        '-of', 'json', str(filename),
    ], check=True, capture_output=True, text=True).stdout)
    streams = metadata.get('streams') or []
    videos = [stream for stream in streams if stream['codec_type'] == 'video']
    audios = [stream for stream in streams if stream['codec_type'] == 'audio']
    if len(videos) != 1 or videos[0]['codec_name'] != 'h264':
        raise ValueError('请选择 H.264 编码的 MP4 视频')
    if audios and any(audio['codec_name'] != 'aac' for audio in audios):
        raise ValueError('视频音频需使用 AAC 编码')
    duration = float(metadata['format']['duration'])
    if not 0 < duration <= 3600:
        raise ValueError('请选择长度在 1 秒至 60 分钟内的视频')
    width, height = videos[0]['width'], videos[0]['height']
    if not 32 <= width <= 4096 or not 32 <= height <= 4096:
        raise ValueError('视频画面尺寸不符合上传要求')
    return {'duration': duration, 'width': width, 'height': height,
            'video_codec': videos[0]['codec_name'],
            'audio_codecs': [audio['codec_name'] for audio in audios]}


def delete_queue_uploads(queue_id: str) -> None:
    directory = USER_MEDIA / queue_id
    if not directory.is_dir():
        return
    for image in directory.iterdir():
        if not image.is_file():
            raise ValueError('附件目录包含不符合预期的内容')
        image.unlink()
    directory.rmdir()


def select_queue_media(queue_id: str, media_ids: list[str]) -> list[dict]:
    if len(media_ids) > MAX_SELECTED_MEDIA or len(set(media_ids)) != len(media_ids):
        raise ValueError('每条帖子最多选择四张不同的图片')
    available = {entry['id']: entry for entry in media_choices(queue_id)}
    for media_id in media_ids:
        if media_id not in available:
            raise ValueError('选择的媒体文件不属于当前帖子')
        if not available[media_id]['ready']:
            raise ValueError('请先导入对应的原帖图片')
    if any(available[media_id]['kind'] == 'video' for media_id in media_ids):
        if len(media_ids) != 1:
            raise ValueError('一条 X 帖子只能选择一个视频，不能与图片混合上传')
    store.set_queue_media_ids(queue_id, media_ids)
    return media_choices(queue_id)


def selected_media_files(queue_id: str) -> list[Path]:
    item = store.queue_media_info(queue_id)
    if item is None:
        raise LookupError('待发布内容不存在')
    choices = {entry['id']: entry for entry in media_choices(queue_id)}
    files = []
    for media_id in store.queue_media_ids(queue_id):
        entry = choices[media_id]
        if not entry['ready']:
            raise ValueError('有已经选择的原帖图片尚未导入')
        if entry['origin'] == 'generated':
            name = media_id.removeprefix('generated:') + '.png'
            filename = GENERATED_MEDIA / item['image_directory'] / name
        elif entry['origin'] == 'user':
            uploaded = next(row for row in store.uploaded_media(queue_id)
                            if row['id'] == media_id)
            filename = USER_MEDIA / uploaded['cached_file']
        elif entry['origin'] == 'douyin':
            original = store.get_douyin_candidate(item['trend_id'])
            if original is None or original['id'] != media_id or not original['video_file']:
                raise ValueError('抖音原视频附件记录已经失效')
            filename = source_video_path(original['video_file'], strict=True)
        else:
            original = next(row for row in store.trend_media(item['trend_id'])
                            if row['id'] == media_id)
            filename = SOURCE_MEDIA / original['cached_file']
        if not filename.is_file():
            raise FileNotFoundError(f'待发布媒体文件不存在：{filename}')
        files.append(filename)
    return files
