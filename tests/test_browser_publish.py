from urllib.parse import parse_qs, urlparse

import pytest

from app.browser_publish import compose_url, validate_post_url


def test_official_compose_link_preserves_unicode():
    content = 'Testing XHotLab: 中文内容 & original thoughts 🧪'
    parsed = urlparse(compose_url(content))
    assert parsed.scheme == 'https'
    assert parsed.netloc == 'x.com'
    assert parsed.path == '/intent/post'
    assert parse_qs(parsed.query)['text'] == [content]


def test_compose_content_bounds():
    with pytest.raises(ValueError):
        compose_url(' ')
    with pytest.raises(ValueError):
        compose_url('x' * 281)


def test_record_only_real_post_url_shape():
    url = 'https://x.com/example_user/status/1234567890000?ref=share'
    assert validate_post_url(url) == 'https://x.com/example_user/status/1234567890000'
    with pytest.raises(ValueError):
        validate_post_url('http://x.com/example_user/status/1234567890000')
    with pytest.raises(ValueError):
        validate_post_url('https://example.com/not-a-real-post')
    with pytest.raises(ValueError):
        validate_post_url('https://x.com/example_user')
