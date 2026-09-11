"""A pagina que o hub embute: Clipar e Configuracoes."""
from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QLabel,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from clipit.core.atalho import Atalho
from clipit.core.clips import RegistroDeClipes
from clipit.core.paths import tokens_path
from clipit.core.service import ClipItService
from clipit.core.settings import Settings
from clipit.core.twitch_auth import GuardaDeTokens
from clipit.ui.clips_tab import ClipsTab
from clipit.ui.gatilho import Gatilho
from clipit.ui.settings_tab import SettingsTab


class ClipItPage(QWidget):
    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        settings = Settings()
        self.servico = ClipItService(
            settings, GuardaDeTokens(tokens_path()), RegistroDeClipes()
        )

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 22, 0)
        raiz.setSpacing(14)

        titulo = QLabel("ClipIt")
        titulo.setObjectName("PageTitle")
        raiz.addWidget(titulo)

        subtitulo = QLabel(
            "Cria o clipe na Twitch do que acabou de acontecer e guarda o link "
            "junto da sua marcação."
        )
        subtitulo.setObjectName("Muted")
        subtitulo.setWordWrap(True)
        raiz.addWidget(subtitulo)

        self.abas = QTabWidget()
        self.aba_clipes = ClipsTab(self.servico)
        self.aba_config = SettingsTab(self.servico)
        self.abas.addTab(self._rolavel(self.aba_clipes), "Clipar")
        self.abas.addTab(self._rolavel(self.aba_config), "Configurações")
        raiz.addWidget(self.abas, 1)

        # Uma aba avisa a outra: conectou ou desconectou, o botao reavalia.
        self.aba_config.conta_mudou.connect(self.aba_clipes.checar_estado)
        self.aba_clipes.pedir_configuracoes.connect(
            lambda: self.abas.setCurrentIndex(1)
        )
        self.abas.currentChanged.connect(
            lambda i: i == 0 and self.aba_clipes.checar_estado()
        )

        # O atalho global. O backend chama o Gatilho fora da GUI; o Signal
        # traz a chamada de volta para a thread certa antes de clipar.
        self.atalho = Atalho()
        self.gatilho = Gatilho(self)
        self.gatilho.disparou.connect(self.aba_clipes.clipar_por_atalho)
        self.aba_config.atalho_mudou.connect(self._registrar_atalho)
        # Registrar e trabalho do backend, nao da montagem: fica para depois
        # do primeiro desenho, como a regra de "nada bloqueante" pede.
        QTimer.singleShot(0, lambda: self._registrar_atalho(
            str(settings.get("atalho", ""))
        ))

    def _registrar_atalho(self, sequencia: str) -> None:
        if not sequencia:
            self.atalho.remover()
            self.aba_config.mostrar_estado_do_atalho("Sem atalho.")
            return
        problema = self.atalho.registrar(sequencia, self.gatilho.callback)
        self.aba_config.mostrar_estado_do_atalho(
            problema if problema else f"Atalho ativo: {self.atalho.sequencia}"
        )

    @staticmethod
    def _rolavel(conteudo: QWidget) -> QWidget:
        area = QScrollArea()
        area.setObjectName("PageScroll")
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.Shape.NoFrame)
        moldura = QWidget()
        caixa = QVBoxLayout(moldura)
        caixa.setContentsMargins(4, 8, 12, 8)
        caixa.addWidget(conteudo)
        area.setWidget(moldura)
        return area

    def encerrar(self) -> None:
        """Para as threads antes de o app sair.

        Destruir uma QThread viva aborta o processo -- ja custou uma versao do
        Streamer Sidekick.
        """
        self.atalho.remover()
        self.aba_clipes.encerrar()
        self.aba_config.encerrar()

    def closeEvent(self, evento):  # noqa: N802
        self.encerrar()
        super().closeEvent(evento)
