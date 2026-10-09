from vdo.intro import _plan
from vdo.providers.media import _rank
from vdo.providers.tts import _clean_for_tts


def test_intro_plan_is_clear_and_compact():
    plan = _plan(40)
    assert 5 <= len(plan) <= 8
    assert plan[0]["story_role"] == "hook"
    assert plan[-1]["story_role"] == "resolution"
    assert all(scene["narration"].strip() for scene in plan)


def test_media_rank_prefers_video_and_relevance():
    video = {
        "mime": "video/mp4",
        "title": "Researcher Working in Archive",
        "description": "documentary footage of researcher",
        "license": "CC BY 4.0",
        "width": 1920,
        "height": 1080,
        "duration": 24,
        "size": 10_000_000,
    }
    still = {
        "mime": "image/jpeg",
        "title": "Archive Diagram",
        "description": "researcher chart",
        "license": "CC BY 4.0",
        "width": 1920,
        "height": 1080,
        "duration": 0,
        "size": 1_000_000,
    }
    assert _rank(video, ["researcher", "archive"]) < _rank(still, ["researcher", "archive"])


def test_tts_text_cleanup_keeps_natural_sentence_flow():
    text = _clean_for_tts("  Start — with one idea; then build the story...  ")
    assert text == "Start, with one idea. then build the story..."
