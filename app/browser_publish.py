import re
from urllib.parse import urlencode, urlparse


def compose_url(content: str) -> str:
    if not content.strip() or len(content) > 280:
        raise ValueError('发帖内容需要在 1 到 280 个字符以内')
    return 'https://x.com/intent/post?' + urlencode({'text': content})


def validate_post_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme != 'https' or parsed.hostname not in (
        'x.com', 'www.x.com', 'twitter.com', 'www.twitter.com'
    ):
        raise ValueError('请填写实际发布的 X 帖子 HTTPS 链接')
    if not re.fullmatch(r'/(?:i/web|[A-Za-z0-9_]{1,15})/status/[0-9]+/?', parsed.path):
        raise ValueError('帖子链接应包含账号和 /status/帖子编号')
    if parsed.username or parsed.password or parsed.port:
        raise ValueError('帖子链接格式错误')
    return f'https://x.com{parsed.path.rstrip("/")}'
