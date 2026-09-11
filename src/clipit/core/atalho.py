"""O atalho global, pelo backend do Sidekick.

O plugin nao registra hotkey por conta propria: usa o mesmo backend que o hub
(`streamer_sidekick.core.hotkey_backend`), que ja resolveu as armadilhas de
cada sistema -- o Carbon no macOS, o `keyboard` no Windows. Fora do Sidekick
(standalone) o atalho simplesmente nao existe, e a UI diz isso.

O callback dispara na thread do backend, nunca na da GUI. Quem chama tem de
atravessar para a GUI por Signal antes de tocar em widget -- regra 3 do padrao.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

try:
    from streamer_sidekick.core import hotkey_backend as _backend  # type: ignore
except Exception:  # standalone: sem hub, sem atalho
    _backend = None


def disponivel() -> bool:
    if _backend is None:
        return False
    try:
        return bool(_backend.is_available())
    except Exception:
        return False


def normalizar(sequencia: str) -> str:
    if _backend is None:
        return sequencia.strip()
    try:
        return str(_backend.normalize(sequencia))
    except Exception:
        return sequencia.strip()


def validar(sequencia: str) -> str:
    """Devolve "" se a sequencia serve, ou a mensagem do backend se nao."""
    if _backend is None:
        return "O atalho só funciona com o plugin rodando dentro do Streamer Sidekick."
    try:
        _backend.validate(sequencia)
        return ""
    except Exception as erro:  # noqa: BLE001 -- e a mensagem que interessa
        return str(erro)


class Atalho:
    """Um atalho de cada vez. Registrar de novo troca o anterior."""

    def __init__(self) -> None:
        self._handle: Optional[Any] = None
        self.sequencia = ""

    @property
    def ativo(self) -> bool:
        return self._handle is not None

    def registrar(self, sequencia: str, callback: Callable[[], None]) -> str:
        """Devolve "" no sucesso, ou o motivo da falha (para mostrar na tela)."""
        self.remover()
        sequencia = normalizar(sequencia)
        if not sequencia:
            return ""
        if not disponivel():
            return "Backend de atalhos indisponível."
        problema = validar(sequencia)
        if problema:
            return problema
        try:
            self._handle = _backend.register(sequencia, callback)  # type: ignore[union-attr]
        except Exception as erro:  # noqa: BLE001
            return f"Não consegui registrar {sequencia}: {erro}"
        self.sequencia = sequencia
        return ""

    def remover(self) -> None:
        if self._handle is None:
            return
        try:
            _backend.unregister(self._handle)  # type: ignore[union-attr]
        except Exception:
            pass
        self._handle = None
        self.sequencia = ""
