from vdo.providers.media import _rank


def test_open_video_is_preferred() -> None:
    asset = {
        "mime": "video/mp4",
        "license": "CC0",
        "size": 1000,
    }
    image = {
        "mime": "image/jpeg",
        "license": "CC0",
        "size": 1000,
    }
    assert _rank(asset) < _rank(image)
