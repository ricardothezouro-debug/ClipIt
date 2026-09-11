"""O unico lugar que traduz callback do core em Signal do Qt.

Regra que ja custou uma versao do Sidekick: destruir uma QThread viva aborta o
processo. Por isso todo worker aqui sabe ser cancelado, e a pagina guarda a
referencia e espera o fim antes de sair.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QThread, Signal

from clipit.core import twitch_auth
from clipit.core.errors import Cancelado, ClipItError
from clipit.core.service import ClipItService
from clipit.core.twitch_auth import CodigoDeDispositivo


class _Worker(QThread):
    falhou = Signal(str, str, str)  # titulo, detalhe, acao

    def __init__(self) -> None:
        super().__init__()
        self._parar = False

    def encerrar(self) -> None:
        self._parar = True
        self.wait(5000)

    def _relatar(self, erro: Exception) -> None:
        if isinstance(erro, ClipItError):
            self.falhou.emit(erro.titulo, erro.detalhe, erro.acao)
        else:
            self.falhou.emit("Algo deu errado", str(erro), "")


class LoginWorker(_Worker):
    """Pede o codigo, mostra para o usuario e espera a autorizacao."""

    codigo_pronto = Signal(object)   # CodigoDeDispositivo
    conectado = Signal(object)       # Usuario

    def __init__(self, servico: ClipItService) -> None:
        super().__init__()
        self.servico = servico

    def run(self) -> None:
        try:
            client_id = self.servico.settings.client_id
            codigo: CodigoDeDispositivo = twitch_auth.iniciar(client_id)
            self.codigo_pronto.emit(codigo)

            tokens = twitch_auth.aguardar(
                client_id, codigo, cancelar=lambda: self._parar
            )
            self.servico.guarda.salvar(tokens)
            self.conectado.emit(self.servico.usuario(recarregar=True))
        except Cancelado:
            pass
        except Exception as erro:  # noqa: BLE001 -- a UI mostra qualquer um
            self._relatar(erro)


class ClipeWorker(_Worker):
    """Cria o clipe. Curto, mas fora da thread da GUI: e rede."""

    pronto = Signal(object)  # Resultado

    def __init__(self, servico: ClipItService, texto: str) -> None:
        super().__init__()
        self.servico = servico
        self.texto = texto

    def run(self) -> None:
        try:
            self.pronto.emit(self.servico.clipar(self.texto))
        except Exception as erro:  # noqa: BLE001
            self._relatar(erro)


class EstadoWorker(_Worker):
    """Descobre quem esta logado e se a live esta no ar."""

    estado = Signal(object, bool)  # Usuario|None, ao_vivo

    def __init__(self, servico: ClipItService) -> None:
        super().__init__()
        self.servico = servico

    def run(self) -> None:
        try:
            if not self.servico.conectado():
                self.estado.emit(None, False)
                return
            usuario = self.servico.usuario(recarregar=True)
            self.estado.emit(usuario, self.servico.api().esta_ao_vivo(usuario.id))
        except Exception:  # noqa: BLE001
            # Aqui um erro nao merece alarde: e so a checagem de fundo.
            self.estado.emit(None, False)


class ConfirmacaoWorker(_Worker):
    """Pergunta a Twitch se os clipes recentes terminaram de processar."""

    confirmado = Signal(str)  # clip_id

    def __init__(self, servico: ClipItService, ids: list[str]) -> None:
        super().__init__()
        self.servico = servico
        self.ids = list(ids)

    def run(self) -> None:
        for clip_id in self.ids:
            if self._parar:
                return
            try:
                if self.servico.confirmar(clip_id):
                    self.confirmado.emit(clip_id)
            except Exception:  # noqa: BLE001
                continue
