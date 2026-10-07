from vdo.schemas import Documentary, Scene


def test_real_documentary_story_metadata() -> None:
    doc = Documentary(
        title="Example",
        logline="Example",
        hook="A counterintuitive hook",
        anchor_fact="A verified fact",
        human_stakes="People are affected",
        chapters=["Origins", "Turning point", "Consequences"],
        scenes=[
            Scene(
                id=1,
                title="Opening",
                narration="This is a natural spoken opening.",
                visual_query="real documentary archive footage",
                chapter="Origins",
                story_role="hook",
                shot_type="establishing",
                seconds=8,
            )
        ],
    )
    assert doc.hook
    assert doc.anchor_fact
    assert doc.scenes[0].story_role == "hook"
    assert doc.scenes[0].shot_type == "establishing"
