"""A ponte com o Marcador do Sidekick.

Escreve no MESMO arquivo e no MESMO formato que o Marcador usa
(`[AAAA-MM-DD HH:MM:SS] texto`), para o registro da live continuar sendo um
arquivo so. A diferenca e que a linha do ClipIt ja vem com o link do clipe.

Nao importa o MarkerService para chamar metodos dele: le a configuracao e
escreve direto. Assim uma mudanca interna do Sidekick nao quebra o plugin, e o
plugin funciona mesmo rodando standalone.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from clipit.core.paths import _app_data_dir


def _config_do_sidekick() -> dict:
    try:
        bruto = (_app_data_dir() / "config.json").read_text(encoding="utf-8")
        dados = json.loads(bruto)
        return dados if isinstance(dados, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _secao_marker() -> dict:
    """A config do Sidekick e ANINHADA: {"marker": {"folder": ...}}.

    Por dentro o Sidekick le com notacao de ponto ("marker.folder"), mas no
    arquivo isso e um dicionario dentro do outro -- procurar a chave literal
    "marker.folder" no JSON nunca acha nada.
    """
    secao = _config_do_sidekick().get("marker")
    return secao if isinstance(secao, dict) else {}


def pasta_do_marcador() -> Optional[Path]:
    valor = _secao_marker().get("folder")
    if not valor:
        return None
    pasta = Path(str(valor))
    return pasta if pasta.is_dir() else None


def arquivo_ativo() -> Optional[Path]:
    """O arquivo do jogo que o Marcador esta usando agora.

    Primeiro a config (`marker.active_file`); se faltar, o `ultimo_jogo.txt`
    que as versoes antigas gravavam na pasta -- o mesmo fallback do Sidekick.
    """
    pasta = pasta_do_marcador()
    if pasta is None:
        return None

    nome = str(_secao_marker().get("active_file", "")).strip()
    if not nome:
        try:
            nome = (pasta / "ultimo_jogo.txt").read_text(encoding="utf-8").strip()
        except OSError:
            nome = ""
    if not nome:
        return None
    return pasta / (nome if nome.endswith(".txt") else f"{nome}.txt")


def linha(texto: str, link: str = "", quando: Optional[datetime] = None) -> str:
    """Monta a linha no formato do Marcador. Sem I/O -- da para testar."""
    stamp = (quando or datetime.now()).strftime("[%Y-%m-%d %H:%M:%S]")
    corpo = " ".join((texto or "").split()) or "clipe"
    return f"{stamp} {corpo} — {link}\n" if link else f"{stamp} {corpo}\n"


def registrar(texto: str, link: str = "", quando: Optional[datetime] = None) -> bool:
    """Anexa a linha no arquivo ativo. False se nao houver onde escrever."""
    alvo = arquivo_ativo()
    if alvo is None:
        return False
    try:
        alvo.parent.mkdir(parents=True, exist_ok=True)
        with alvo.open("a", encoding="utf-8") as arquivo:
            arquivo.write(linha(texto, link, quando))
        return True
    except OSError:
        return False
