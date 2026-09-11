"""Onde o plugin guarda o que e dele.

Fora da pasta do plugin, sempre: ela e sobrescrita inteira a cada atualizacao.
Segue o mesmo diretorio de dados do Sidekick para o usuario ter tudo num lugar
so, mas funciona sozinho se o Sidekick nao estiver importavel (modo standalone).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _app_data_dir() -> Path:
    try:
        from streamer_sidekick.core.paths import app_data_dir  # type: ignore

        return Path(app_data_dir())
    except Exception:
        pass

    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
        return Path(base) / "StreamerSidekick"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "StreamerSidekick"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "StreamerSidekick"


def data_dir() -> Path:
    pasta = _app_data_dir() / "clipit"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def settings_path() -> Path:
    return data_dir() / "settings.json"


def tokens_path() -> Path:
    """Arquivo separado das preferencias: ele guarda credencial."""
    return data_dir() / "tokens.json"


def clips_path() -> Path:
    return data_dir() / "clips.json"
