import os
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .config import ROOT


CREATORHUB_ROOT = Path(
    os.environ.get('CREATORHUB_HOME') or ROOT.parent / 'CreatorHub'
).resolve()
CREATORHUB_URL = 'http://127.0.0.1:8000'
PLATFORMS = ('douyin', 'xhs', 'kuaishou', 'shipinhao', 'tiktok')
PLATFORM_DOMAINS = {
    'douyin': ('douyin.com', 'iesdouyin.com'),
    'xhs': ('xiaohongshu.com', 'xhslink.com'),
    'kuaishou': ('kuaishou.com', 'kwai.com'),
    'shipinhao': ('weixin.qq.com',),
    'tiktok': ('tiktok.com',),
}


def python_executable() -> Path:
    if os.name == 'nt':
        return CREATORHUB_ROOT / '.venv' / 'Scripts' / 'pythonw.exe'
    return CREATORHUB_ROOT / '.venv' / 'bin' / 'python'


def _client(timeout: float = 5.0) -> httpx.Client:
    return httpx.Client(base_url=CREATORHUB_URL, timeout=timeout, trust_env=False)


def running() -> bool:
    with _client() as client:
        try:
            response = client.get('/health')
        except httpx.ConnectError:
            return False
        except httpx.TimeoutException:
            return False
        return response.status_code == 200 and response.json() == {'status': 'ok'}


def status() -> dict:
    return {
        'installed': python_executable().is_file()
        and (CREATORHUB_ROOT / 'app' / 'main.py').is_file(),
        'running': running(),
        'url': CREATORHUB_URL,
        'platforms': list(PLATFORMS),
        'source': 'https://github.com/3441293738/creatorhub',
        'path': str(CREATORHUB_ROOT),
    }


def start() -> dict:
    if running():
        return status()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(1)
        if probe.connect_ex(('127.0.0.1', 8000)) == 0:
            raise ValueError('本机 8000 端口被其他服务占用')
    executable = python_executable()
    if not executable.is_file():
        raise ValueError('CreatorHub 运行环境未安装完成')
    if not (CREATORHUB_ROOT / 'app' / 'main.py').is_file():
        raise ValueError('CreatorHub 源码目录不存在')
    logs = CREATORHUB_ROOT / 'data' / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    log_file = logs / 'xhotlab_creatorhub.log'
    with log_file.open('a', encoding='utf-8') as output:
        subprocess.Popen(
            [str(executable), '-m', 'uvicorn', 'app.main:app',
             '--host', '127.0.0.1', '--port', '8000'],
            cwd=CREATORHUB_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            close_fds=True,
        )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if running():
            return status()
        time.sleep(0.25)
    raise ValueError(
        'CreatorHub 启动后未能通过健康检查，请检查日志：' + str(log_file))


def dashboard() -> dict:
    if not running():
        raise ValueError('CreatorHub 服务尚未启动')
    with _client() as client:
        platforms = []
        for platform in PLATFORMS:
            response = client.get('/api/overview/summary', params={'platform': platform})
            response.raise_for_status()
            report = response.json()
            platforms.append({
                'id': platform,
                'accounts': report['accounts'],
                'monitors': report['monitors'],
                'downloaded': report['downloaded'],
                'comments': report['comments'],
            })
        response = client.get('/api/accounts')
        response.raise_for_status()
        account_rows = response.json()
        response = client.get(
            '/api/risk-control/accounts', params={'platform': 'douyin'})
        response.raise_for_status()
        risk_by_id = {
            int(item['account_id']): item for item in response.json()
        }
        accounts = [{
            'id': account['id'],
            'platform': account['platform'],
            'nickname': account['nickname'],
            'status': account.get('status', ''),
            'followers': account.get('follower_count', 0),
            'creator_logged_in': account.get('has_creator', False),
            'read_logged_in': account.get('has_read_login', False),
            'risk_status': risk_by_id.get(int(account['id']), {}).get(
                'status', 'unknown') if account['platform'] == 'douyin' else 'normal',
            'risk_status_label': risk_by_id.get(int(account['id']), {}).get(
                'status_label', '风险状态未知') if account['platform'] == 'douyin' else '正常',
            'risk_reason': risk_by_id.get(int(account['id']), {}).get('reason', '')
                if account['platform'] == 'douyin' else '',
            'manual_review_required': bool(risk_by_id.get(
                int(account['id']), {}).get('manual_review_required', False)),
            'risk_cooldown_until': risk_by_id.get(
                int(account['id']), {}).get('cooldown_until'),
        } for account in account_rows]
    return {'platforms': platforms, 'accounts': accounts, 'url': CREATORHUB_URL}


def activity() -> dict:
    if not running():
        raise ValueError('CreatorHub 服务尚未启动')
    resources = {
        'monitors': '/api/monitors',
        'collections': '/api/collections?limit=20',
        'publish_tasks': '/api/publish',
        'downloads': '/api/share-download/history?limit=20',
    }
    activity_records = {}
    with _client() as client:
        for name, path in resources.items():
            response = client.get(path)
            response.raise_for_status()
            records = response.json()
            if not isinstance(records, list):
                raise ValueError('CreatorHub 任务接口数据格式异常')
            activity_records[name] = [{
                'id': record.get('id'),
                'platform': record.get('platform', ''),
                'title': (record.get('name') or record.get('title')
                          or record.get('keyword') or record.get('target_name')
                          or record.get('source_url') or ''),
                'status': record.get('status', ''),
                'enabled': record.get('enabled', False),
                'created_at': str(record.get('created_at') or ''),
            } for record in records[:20]]
    return activity_records


def validate_share_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    hostname = (parsed.hostname or '').lower()
    if parsed.scheme != 'https' or parsed.username or parsed.password:
        raise ValueError('请输入支持平台的 HTTPS 作品链接')
    if not any(hostname == domain or hostname.endswith('.' + domain)
               for domains in PLATFORM_DOMAINS.values() for domain in domains):
        raise ValueError('当前只支持抖音、小红书、快手、视频号和 TikTok 链接')
    return url.strip()


def _share_platform(url: str) -> str:
    hostname = (urlsplit(url).hostname or '').lower()
    for platform, domains in PLATFORM_DOMAINS.items():
        if any(hostname == domain or hostname.endswith('.' + domain)
               for domain in domains):
            return platform
    raise ValueError('当前链接无法识别所属平台')


def share(url: str, download: bool, account_id: int | None = None) -> dict:
    if not running():
        raise ValueError('请先启动 CreatorHub')
    link = validate_share_url(url)
    platform = _share_platform(link)
    with _client(150.0) as client:
        response = client.get('/api/accounts')
        response.raise_for_status()
        accounts = response.json()
        matching = [account for account in accounts
                    if account.get('platform') == platform
                    and account.get('status') == 'active'
                    and account.get('has_read_login')]
        if account_id is None:
            if len(matching) == 1:
                account_id = int(matching[0]['id'])
            elif len(matching) > 1:
                raise ValueError('检测到多个已登录的平台账号，请在账号选择框中指定账号')
        else:
            selected = next((account for account in accounts
                             if int(account.get('id') or 0) == account_id), None)
            if selected is None:
                raise ValueError('所选平台账号不存在')
            if selected.get('platform') != platform:
                raise ValueError('所选账号所属平台与作品链接不一致')
            if selected.get('status') != 'active' or not selected.get('has_read_login'):
                raise ValueError('所选平台账号的作品读取登录态尚未就绪')
        payload = {
            'share_text': link,
            'download': download,
            'all_links': False,
            'quality': 'highest',
            'save_metadata': True,
            'save_thumbnail': True,
        }
        if account_id is not None:
            payload['account_id'] = account_id
        response = client.post('/api/share-download', json=payload)
        response.raise_for_status()
        return response.json()
