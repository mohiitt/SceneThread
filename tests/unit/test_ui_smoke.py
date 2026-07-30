from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_app_renders_without_exception() -> None:
    app_path = Path(__file__).resolve().parents[2] / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=15).run()

    assert not app.exception
    assert app.title[0].value == "SceneThread"
    labels = {tab.label for tab in app.tabs}
    assert {"Ingest", "Ask", "Graph Explorer", "Test Lab"}.issubset(labels)


def test_streamlit_fixture_pipeline_completes() -> None:
    app_path = Path(__file__).resolve().parents[2] / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=15).run()
    app.sidebar.radio[0].set_value("Fixture preview").run()
    pipeline_button = next(
        button for button in app.button if button.label == "Run fixture pipeline"
    )
    pipeline_button.click().run()

    assert not app.exception
    assert any(
        "Fixture pipeline completed" in success.value for success in app.success
    )
    assert any("Safe Strands execution trace" in header.value for header in app.subheader)


def test_streamlit_exposes_explicit_live_openai_mode() -> None:
    app_path = Path(__file__).resolve().parents[2] / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=15).run()

    options = app.sidebar.radio[0].options
    assert "Live OpenAI + saved sponsor data" in options
    assert "Full live services" in options


def test_ask_evidence_opens_timestamped_scene_popup() -> None:
    app_path = Path(__file__).resolve().parents[2] / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=15).run()
    app.session_state["video_sources"] = {
        "fixture_video_001": "https://example.com/video.mp4"
    }

    ask_button = next(button for button in app.button if button.label == "Ask fixture")
    ask_button.click().run()
    scene_button = next(button for button in app.button if button.label == "View scene")
    scene_button.click().run()

    assert not app.exception
    assert len(app.get("video")) == 1
    assert any("scene_002 · 00:12–00:38" in item.value for item in app.markdown)


def test_switching_runtime_mode_clears_results_from_previous_mode() -> None:
    app_path = Path(__file__).resolve().parents[2] / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=15).run()
    app.sidebar.radio[0].set_value("Fixture preview").run()
    pipeline_button = next(
        button for button in app.button if button.label == "Run fixture pipeline"
    )
    pipeline_button.click().run()
    assert app.session_state["pipeline_result"] is not None

    app.sidebar.radio[0].set_value("Live OpenAI + saved sponsor data").run()

    assert "pipeline_result" not in app.session_state
