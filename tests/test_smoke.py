from vdo.schemas import Documentary, Scene


def test_schema_roundtrip() -> None:
    doc = Documentary(
        title="Demo",
        logline="Demo",
        scenes=[
            Scene(
                id=1,
                title="Opening",
                narration="Hello",
                visual_query="history",
                seconds=5,
            )
        ],
    )
    restored = Documentary.model_validate_json(doc.model_dump_json())
    assert restored.scenes[0].narration == "Hello"
