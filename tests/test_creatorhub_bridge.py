import pytest

from app import creatorhub_bridge


@pytest.mark.parametrize(("url", "platform"), [
    ('https://www.douyin.com/video/1234567890123456', 'douyin'),
    ('https://www.xiaohongshu.com/explore/123456', 'xhs'),
    ('https://v.kuaishou.com/abc123', 'kuaishou'),
    ('https://channels.weixin.qq.com/platform/post/123', 'shipinhao'),
    ('https://www.tiktok.com/@creator/video/123456', 'tiktok'),
])
def test_share_url_resolves_its_platform(url, platform):
    assert creatorhub_bridge.validate_share_url(url) == url
    assert creatorhub_bridge._share_platform(url) == platform


def test_share_url_rejects_unsupported_hosts():
    with pytest.raises(ValueError, match='当前只支持'):
        creatorhub_bridge.validate_share_url('https://example.com/video/123456')
