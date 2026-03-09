from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("uvicorn")

from server import main as server_main


def test_server_main_parses_cli_args(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(app_path: str, host: str, port: int, reload: bool) -> None:
        captured["app_path"] = app_path
        captured["host"] = host
        captured["port"] = port
        captured["reload"] = reload

    monkeypatch.setattr(server_main.uvicorn, "run", fake_run)

    server_main.main(["--host", "127.0.0.1", "--port", "9000", "--reload"])

    assert captured == {
        "app_path": "server.main:app",
        "host": "127.0.0.1",
        "port": 9000,
        "reload": True,
    }
