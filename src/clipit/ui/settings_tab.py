"""Conta da Twitch e como o clipe deve ser feito."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtCore import QUrl
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QKeySequenceEdit,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from clipit.core import atalho as atalho_mod
from clipit.core.service import ClipItService
from clipit.ui.components import NeonPanel
from clipit.ui.workers import LoginWorker


try:  # o Sidekick sabe converter a notacao dele para o Qt e de volta
    from streamer_sidekick.core import hotkey_text as _hotkey_text  # type: ignore
except Exception:
    _hotkey_text = None


def _para_texto(sequencia: QKeySequence) -> str:
    if _hotkey_text is not None:
        return str(_hotkey_text.from_key_sequence(sequencia))
    return sequencia.toString(QKeySequence.SequenceFormat.PortableText)


def _para_qt(texto: str) -> QKeySequence:
    if _hotkey_text is not None:
        return _hotkey_text.to_key_sequence(texto)
    return QKeySequence(texto)


class SettingsTab(QWidget):
    conta_mudou = Signal()
    atalho_mudou = Signal(str)  # a sequencia nova ("" = sem atalho)

    def __init__(self, servico: ClipItService, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.servico = servico
        self._login: Optional[LoginWorker] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(self._painel_conta())
        layout.addWidget(self._painel_atalho())
        layout.addWidget(self._painel_como())
        layout.addWidget(self._painel_avancado())
        layout.addStretch(1)

    # ------------------------------------------------------------- conta
    def _painel_conta(self) -> QWidget:
        painel = NeonPanel(accent="#9146FF")
        caixa = QVBoxLayout(painel)
        caixa.setContentsMargins(18, 16, 18, 16)
        caixa.setSpacing(10)

        titulo = QLabel("01  |  Conta da Twitch")
        titulo.setObjectName("Kicker")
        caixa.addWidget(titulo)

        explicacao = QLabel(
            "Você autoriza no navegador, com um código curto. Nenhuma senha "
            "passa pelo plugin, e o acesso só permite criar clipes."
        )
        explicacao.setObjectName("Muted")
        explicacao.setWordWrap(True)
        caixa.addWidget(explicacao)

        # O codigo grande, escondido ate o login comecar.
        self.caixa_codigo = QWidget()
        codigo_layout = QVBoxLayout(self.caixa_codigo)
        codigo_layout.setContentsMargins(0, 6, 0, 6)
        codigo_layout.setSpacing(6)
        self.rotulo_codigo = QLabel("—")
        self.rotulo_codigo.setObjectName("PageTitle")
        self.rotulo_codigo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rotulo_codigo.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        codigo_layout.addWidget(self.rotulo_codigo)
        instrucao = QLabel("Digite esse código na página que abriu no navegador.")
        instrucao.setObjectName("Muted")
        instrucao.setAlignment(Qt.AlignmentFlag.AlignCenter)
        codigo_layout.addWidget(instrucao)
        linha_codigo = QHBoxLayout()
        linha_codigo.addStretch(1)
        self.botao_abrir = QPushButton("Abrir a página de novo")
        self.botao_abrir.clicked.connect(self._abrir_verificacao)
        linha_codigo.addWidget(self.botao_abrir)
        self.botao_copiar_codigo = QPushButton("Copiar código")
        self.botao_copiar_codigo.clicked.connect(self._copiar_codigo)
        linha_codigo.addWidget(self.botao_copiar_codigo)
        linha_codigo.addStretch(1)
        codigo_layout.addLayout(linha_codigo)
        self.caixa_codigo.setVisible(False)
        caixa.addWidget(self.caixa_codigo)

        acoes = QHBoxLayout()
        self.botao_conectar = QPushButton("Conectar minha conta")
        self.botao_conectar.setObjectName("PrimaryButton")
        self.botao_conectar.clicked.connect(self._conectar)
        acoes.addWidget(self.botao_conectar)
        self.botao_desconectar = QPushButton("Desconectar")
        self.botao_desconectar.clicked.connect(self._desconectar)
        acoes.addWidget(self.botao_desconectar)
        acoes.addStretch(1)
        caixa.addLayout(acoes)

        self.estado_conta = QLabel()
        self.estado_conta.setObjectName("Muted")
        self.estado_conta.setWordWrap(True)
        caixa.addWidget(self.estado_conta)
        self._atualizar_estado_conta()
        return painel

    def _atualizar_estado_conta(self, nome: str = "") -> None:
        conectado = self.servico.conectado()
        self.botao_desconectar.setVisible(conectado)
        self.botao_conectar.setText(
            "Conectar outra conta" if conectado else "Conectar minha conta"
        )
        if conectado:
            self.estado_conta.setText(
                f"Conectado como {nome}." if nome else "Conta conectada."
            )
        else:
            self.estado_conta.setText("Nenhuma conta conectada ainda.")

    def _conectar(self) -> None:
        if self._login is not None and self._login.isRunning():
            return
        self.botao_conectar.setEnabled(False)
        self.estado_conta.setText("Pedindo o código à Twitch…")

        worker = LoginWorker(self.servico)
        worker.codigo_pronto.connect(self._mostrar_codigo)
        worker.conectado.connect(self._conectou)
        worker.falhou.connect(self._falhou)
        worker.finished.connect(lambda: self.botao_conectar.setEnabled(True))
        self._login = worker  # sem a referencia o GC leva a thread
        worker.start()

    def _mostrar_codigo(self, codigo) -> None:
        self._codigo = codigo
        self.rotulo_codigo.setText(codigo.user_code)
        self.caixa_codigo.setVisible(True)
        self.estado_conta.setText("Esperando você autorizar no navegador…")
        self._abrir_verificacao()

    def _abrir_verificacao(self) -> None:
        codigo = getattr(self, "_codigo", None)
        if codigo is not None:
            QDesktopServices.openUrl(QUrl(codigo.verification_uri))

    def _copiar_codigo(self) -> None:
        codigo = getattr(self, "_codigo", None)
        if codigo is not None:
            QGuiApplication.clipboard().setText(codigo.user_code)

    def _conectou(self, usuario) -> None:
        self.caixa_codigo.setVisible(False)
        self._atualizar_estado_conta(getattr(usuario, "nome", ""))
        self.conta_mudou.emit()

    def _falhou(self, titulo: str, detalhe: str, acao: str) -> None:
        self.caixa_codigo.setVisible(False)
        self.estado_conta.setText(" ".join(p for p in (titulo, detalhe, acao) if p))

    def _desconectar(self) -> None:
        self.servico.desconectar()
        self._atualizar_estado_conta()
        self.conta_mudou.emit()


    # ------------------------------------------------------------ atalho
    def _painel_atalho(self) -> QWidget:
        painel = NeonPanel(accent="#FF4FD8")
        caixa = QVBoxLayout(painel)
        caixa.setContentsMargins(18, 16, 18, 16)
        caixa.setSpacing(10)

        titulo = QLabel("02  |  Atalho")
        titulo.setObjectName("Kicker")
        caixa.addWidget(titulo)

        explicacao = QLabel(
            "Um atalho global: funciona com o jogo em foco, sem alt-tab. "
            "Clipa e escreve a marcação com o texto padrão."
        )
        explicacao.setObjectName("Muted")
        explicacao.setWordWrap(True)
        caixa.addWidget(explicacao)

        linha = QHBoxLayout()
        self.editor_atalho = QKeySequenceEdit()
        self.editor_atalho.setMaximumWidth(220)
        atual = str(self.servico.settings.get("atalho", ""))
        if atual:
            self.editor_atalho.setKeySequence(_para_qt(atual))
        linha.addWidget(self.editor_atalho)
        aplicar = QPushButton("Aplicar")
        aplicar.setObjectName("PrimaryButton")
        aplicar.clicked.connect(self._aplicar_atalho)
        linha.addWidget(aplicar)
        limpar = QPushButton("Remover")
        limpar.clicked.connect(self._remover_atalho)
        linha.addWidget(limpar)
        linha.addStretch(1)
        caixa.addLayout(linha)

        self.estado_atalho = QLabel()
        self.estado_atalho.setObjectName("Muted")
        self.estado_atalho.setWordWrap(True)
        caixa.addWidget(self.estado_atalho)

        aviso = QLabel(
            "Escolha uma combinação que o Marcador e o Contador não usem — o "
            "Sidekick não detecta conflito com atalhos de plugin."
        )
        aviso.setObjectName("Muted")
        aviso.setWordWrap(True)
        caixa.addWidget(aviso)

        if not atalho_mod.disponivel():
            self.estado_atalho.setText(
                "Atalhos indisponíveis fora do Streamer Sidekick."
            )
            self.editor_atalho.setEnabled(False)
            aplicar.setEnabled(False)
        return painel

    def _aplicar_atalho(self) -> None:
        texto = _para_texto(self.editor_atalho.keySequence()).strip()
        if not texto:
            self._remover_atalho()
            return
        problema = atalho_mod.validar(atalho_mod.normalizar(texto))
        if problema:
            self.estado_atalho.setText(problema)
            return
        self.servico.settings.set("atalho", atalho_mod.normalizar(texto))
        self.atalho_mudou.emit(self.servico.settings.get("atalho", ""))

    def _remover_atalho(self) -> None:
        self.editor_atalho.clear()
        self.servico.settings.set("atalho", "")
        self.atalho_mudou.emit("")

    def mostrar_estado_do_atalho(self, mensagem: str) -> None:
        """A pagina, que e quem registra, conta como foi."""
        self.estado_atalho.setText(mensagem)

    # -------------------------------------------------------- como clipar
    def _painel_como(self) -> QWidget:
        painel = NeonPanel(accent="#37F2FF")
        caixa = QVBoxLayout(painel)
        caixa.setContentsMargins(18, 16, 18, 16)
        caixa.setSpacing(10)

        titulo = QLabel("03  |  Como clipar")
        titulo.setObjectName("Kicker")
        caixa.addWidget(titulo)

        linha = QHBoxLayout()
        linha.addWidget(QLabel("Momento"))
        self.combo_momento = QComboBox()
        # A Twitch transmite com atraso. has_delay decide QUAL dos dois
        # momentos entra no clipe -- e a diferenca entre pegar o boss morrendo
        # ou a tela de resultado.
        self.combo_momento.addItem("O que eu acabei de fazer", False)
        self.combo_momento.addItem("O que o chat acabou de ver", True)
        indice = self.combo_momento.findData(
            bool(self.servico.settings.get("com_delay", False))
        )
        self.combo_momento.setCurrentIndex(max(0, indice))
        self.combo_momento.currentIndexChanged.connect(
            lambda: self.servico.settings.set(
                "com_delay", bool(self.combo_momento.currentData())
            )
        )
        linha.addWidget(self.combo_momento)
        linha.addStretch(1)
        caixa.addLayout(linha)

        ajuda_momento = QLabel(
            "Sua live chega ao espectador uns 15 segundos atrasada. Se você "
            "clipa reagindo ao jogo, use a primeira. Se clipa porque o chat "
            "reagiu, use a segunda."
        )
        ajuda_momento.setObjectName("Muted")
        ajuda_momento.setWordWrap(True)
        caixa.addWidget(ajuda_momento)

        intervalo = QHBoxLayout()
        intervalo.addWidget(QLabel("Esperar entre clipes"))
        self.spin_intervalo = QSpinBox()
        self.spin_intervalo.setRange(0, 120)
        self.spin_intervalo.setSuffix(" s")
        self.spin_intervalo.setValue(int(self.servico.settings.get("intervalo_minimo", 15)))
        self.spin_intervalo.valueChanged.connect(
            lambda v: self.servico.settings.set("intervalo_minimo", int(v))
        )
        intervalo.addWidget(self.spin_intervalo)
        intervalo.addStretch(1)
        caixa.addLayout(intervalo)

        self.check_marcador = QCheckBox("Escrever a marcação no Marcador, com o link")
        self.check_marcador.setChecked(
            bool(self.servico.settings.get("escrever_no_marcador", True))
        )
        self.check_marcador.toggled.connect(
            lambda v: self.servico.settings.set("escrever_no_marcador", bool(v))
        )
        caixa.addWidget(self.check_marcador)

        padrao = QHBoxLayout()
        padrao.addWidget(QLabel("Texto quando você não escrever nada"))
        self.campo_padrao = QLineEdit(str(self.servico.settings.get("texto_padrao", "clipe")))
        self.campo_padrao.setMaximumWidth(220)
        self.campo_padrao.textChanged.connect(
            lambda t: self.servico.settings.set("texto_padrao", t.strip() or "clipe")
        )
        padrao.addWidget(self.campo_padrao)
        padrao.addStretch(1)
        caixa.addLayout(padrao)
        return painel

    # ---------------------------------------------------------- avancado
    def _painel_avancado(self) -> QWidget:
        painel = NeonPanel(accent="#B9FF43")
        caixa = QVBoxLayout(painel)
        caixa.setContentsMargins(18, 16, 18, 16)
        caixa.setSpacing(10)

        titulo = QLabel("04  |  Avançado")
        titulo.setObjectName("Kicker")
        caixa.addWidget(titulo)

        explicacao = QLabel(
            "O ClipIt já vem com um aplicativo registrado na Twitch — você não "
            "precisa mexer aqui. Troque só se quiser usar o seu próprio."
        )
        explicacao.setObjectName("Muted")
        explicacao.setWordWrap(True)
        caixa.addWidget(explicacao)

        linha = QHBoxLayout()
        linha.addWidget(QLabel("Client ID"))
        self.campo_client = QLineEdit(self.servico.settings.client_id)
        self.campo_client.editingFinished.connect(
            lambda: self.servico.settings.set("client_id", self.campo_client.text().strip())
        )
        linha.addWidget(self.campo_client, 1)
        caixa.addLayout(linha)

        aviso = QLabel(
            "O Client ID é público e não dá acesso a nada sozinho. Este fluxo "
            "não usa Client Secret — se algum serviço pedir o seu, desconfie."
        )
        aviso.setObjectName("Muted")
        aviso.setWordWrap(True)
        caixa.addWidget(aviso)
        return painel

    def encerrar(self) -> None:
        if self._login is not None and self._login.isRunning():
            self._login.encerrar()
