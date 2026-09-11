"""O contrato com o hub do Streamer Sidekick.

Duas funcoes obrigatorias (`module_info` e `build_page`) e uma opcional
(`help_text`). Importar este modulo nao pode ter efeito colateral nenhum: nada
de rede, de disco pesado ou de registrar atalho.
"""
from __future__ import annotations

try:  # Dentro do Sidekick, usa a classe dele.
    from streamer_sidekick.core.modules import ModuleInfo  # type: ignore
except Exception:  # Fora dele, uma copia compativel -- assim roda standalone.
    from dataclasses import dataclass

    @dataclass
    class ModuleInfo:  # type: ignore[no-redef]
        module_id: str
        title: str
        subtitle: str
        status: str
        accent: str
        icon: str = ""


ACCENT = "#9146FF"  # roxo da Twitch


def module_info() -> ModuleInfo:
    return ModuleInfo(
        module_id="clipit",
        title="ClipIt",
        subtitle="Cria o clipe na Twitch por atalho e guarda o link junto da sua marcação.",
        status="Pronto",
        accent=ACCENT,
    )


def build_page(config=None):
    # Import tardio: manter o PySide6 fora do topo do modulo deixa o contrato
    # importavel em teste e em script sem display.
    from clipit.ui.page import ClipItPage

    return ClipItPage()


def help_text() -> str:
    return (
        "Cria um clipe na Twitch do que acabou de acontecer, sem sair do jogo.\n\n"
        "Como usar:\n"
        "• Em Configurações, conecte sua conta da Twitch (um código e o "
        "navegador — nenhuma senha passa pelo plugin).\n"
        "• Durante a live, use o atalho: o clipe é criado e o link vai junto "
        "com a sua marcação no Marcador.\n"
        "• Depois da live, a aba Clipes vira a sua pauta de cortes.\n\n"
        "Bom saber:\n"
        "• Só funciona com a transmissão no ar.\n"
        "• A Twitch escolhe a janela do clipe (uns 30s do que passou); dá para "
        "ajustar depois no link de edição.\n"
        "• O título do clipe na Twitch é o padrão dela — o seu texto fica na "
        "sua marcação."
    )
