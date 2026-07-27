def test_api_entrypoint_uses_fastapi_app(monkeypatch) -> None:
    import main

    called = {}

    def fake_run(app_path: str, **kwargs) -> None:
        called["app_path"] = app_path
        called["kwargs"] = kwargs

    monkeypatch.setattr(main.uvicorn, "run", fake_run)

    main.run_api()

    assert called["app_path"] == "app.main:app"
    assert called["kwargs"]["host"] == "0.0.0.0"
    assert called["kwargs"]["port"] == 8000


def test_ui_entrypoint_targets_streamlit_app(monkeypatch) -> None:
    import ui

    called = {}

    def fake_streamlit_main() -> None:
        called["argv"] = list(ui.sys.argv)

    monkeypatch.setattr(ui.streamlit_cli, "main", fake_streamlit_main)

    ui.run_ui()

    assert called["argv"] == ["streamlit", "run", "ui/streamlit_app.py"]
