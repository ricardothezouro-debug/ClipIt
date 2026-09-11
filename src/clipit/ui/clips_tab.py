"""Clipar e, depois da live, a pauta de cortes."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from clipit.core.clips import Clipe
from clipit.core.service import ClipItService
from clipit.ui.components import NeonPanel
from clipit.ui.workers import ClipeWorker, ConfirmacaoWorker, EstadoWorker


class ClipsTab(QWidget):
    pedir_configuracoes = Signal()

    def __init__(self, servico: ClipItService, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.servico = servico
        self._clipe: Optional[ClipeWorker] = None
        self._estado: Optional[EstadoWorker] = None
        self._confirmacao: Optional[ConfirmacaoWorker] = None
        self._inicio_da_sessao = datetime.now() - timedelta(hours=12)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(self._painel_criar())
        layout.addWidget(self._painel_lista())
        layout.addWidget(self._painel_pauta())
        layout.addStretch(1)

        self._redesenhar_lista()

        # A checagem de "estou ao vivo?" e de fundo e nao pode travar a
        # montagem: QTimer.singleShot(0) empurra para depois do primeiro
        # desenho, como o padrao de plugin exige.
        self._relogio = QTimer(self)
        self._relogio.setInterval(60_000)
        self._relogio.timeout.connect(self.checar_estado)
        self._relogio.start()
        QTimer.singleShot(0, self.checar_estado)

    # ------------------------------------------------------------ criar
    def _painel_criar(self) -> QWidget:
        painel = NeonPanel(accent="#9146FF")
        caixa = QVBoxLayout(painel)
        caixa.setContentsMargins(18, 16, 18, 16)
        caixa.setSpacing(10)

        titulo = QLabel("01  |  Clipar")
        titulo.setObjectName("Kicker")
        caixa.addWidget(titulo)

        self.aviso = QLabel()
        self.aviso.setObjectName("StatusPill")
        self.aviso.setWordWrap(True)
        self.aviso.setVisible(False)
        caixa.addWidget(self.aviso)

        linha = QHBoxLayout()
        self.campo_texto = QLineEdit()
        self.campo_texto.setPlaceholderText(
            "O que aconteceu? (opcional — vai para a sua marcação)"
        )
        self.campo_texto.returnPressed.connect(self.clipar)
        linha.addWidget(self.campo_texto, 1)
        self.botao_clipar = QPushButton("Criar clipe")
        self.botao_clipar.setObjectName("PrimaryButton")
        self.botao_clipar.setMinimumWidth(150)
        self.botao_clipar.clicked.connect(self.clipar)
        linha.addWidget(self.botao_clipar)
        caixa.addLayout(linha)

        self.estado = QLabel("Verificando…")
        self.estado.setObjectName("Muted")
        self.estado.setWordWrap(True)
        caixa.addWidget(self.estado)
        return painel

    def clipar_por_atalho(self) -> None:
        """Chega pela GUI (o Gatilho ja atravessou a thread). Usa o texto do
        campo se houver; senao o padrao das configuracoes."""
        self.clipar()

    def clipar(self) -> None:
        if self._clipe is not None and self._clipe.isRunning():
            return
        self.botao_clipar.setEnabled(False)
        self.estado.setText("Criando o clipe…")

        worker = ClipeWorker(self.servico, self.campo_texto.text())
        worker.pronto.connect(self._clipou)
        worker.falhou.connect(self._falhou)
        worker.finished.connect(lambda: self.botao_clipar.setEnabled(True))
        self._clipe = worker
        worker.start()

    def _clipou(self, resultado) -> None:
        self.campo_texto.clear()
        destino = (
            "e a marcação foi para o Marcador"
            if resultado.escreveu_no_marcador
            else "(nenhum arquivo do Marcador ativo — só registrei aqui)"
        )
        self.estado.setText(f"Clipe criado {destino}.")
        self._redesenhar_lista()
        self._confirmar_depois([resultado.clipe.id])

    def _falhou(self, titulo: str, detalhe: str, acao: str) -> None:
        self.estado.setText(" ".join(p for p in (titulo, detalhe, acao) if p))
        if "conecte" in titulo.lower():
            self.pedir_configuracoes.emit()

    def _confirmar_depois(self, ids: list[str]) -> None:
        """A Twitch leva ate ~15s para processar. Conferimos depois disso."""
        def conferir() -> None:
            if self._confirmacao is not None and self._confirmacao.isRunning():
                return
            worker = ConfirmacaoWorker(self.servico, ids)
            worker.confirmado.connect(lambda _id: self._redesenhar_lista())
            self._confirmacao = worker
            worker.start()

        QTimer.singleShot(16_000, conferir)

    # ------------------------------------------------------------ estado
    def checar_estado(self) -> None:
        if self._estado is not None and self._estado.isRunning():
            return
        if not self.servico.conectado():
            self._mostrar_estado(None, False)
            return
        worker = EstadoWorker(self.servico)
        worker.estado.connect(self._mostrar_estado)
        self._estado = worker
        worker.start()

    def _mostrar_estado(self, usuario, ao_vivo: bool) -> None:
        if not self.servico.conectado():
            self.aviso.setText("Conecte sua conta da Twitch em Configurações.")
            self.aviso.setVisible(True)
            self.botao_clipar.setEnabled(False)
            self.estado.setText("")
            return

        self.aviso.setVisible(not ao_vivo)
        if not ao_vivo:
            # Nao desabilitamos o botao: a checagem e de minuto em minuto e
            # pode estar velha. Melhor deixar tentar e falhar com motivo do
            # que travar quem acabou de entrar ao vivo.
            self.aviso.setText(
                "Você não parece estar ao vivo. A Twitch só cria clipes durante "
                "a transmissão."
            )
        self.botao_clipar.setEnabled(True)
        nome = getattr(usuario, "nome", "") or "sua conta"
        self.estado.setText(
            f"{nome} • {'ao vivo' if ao_vivo else 'fora do ar'}"
        )

    # ------------------------------------------------------------- lista
    def _painel_lista(self) -> QWidget:
        painel = NeonPanel(accent="#37F2FF")
        caixa = QVBoxLayout(painel)
        caixa.setContentsMargins(18, 16, 18, 16)
        caixa.setSpacing(10)

        cabecalho = QHBoxLayout()
        titulo = QLabel("02  |  Clipes recentes")
        titulo.setObjectName("Kicker")
        cabecalho.addWidget(titulo)
        cabecalho.addStretch(1)
        caixa.addLayout(cabecalho)

        self.lista_area = QScrollArea()
        self.lista_area.setWidgetResizable(True)
        self.lista_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.lista_area.setMinimumHeight(180)
        self.lista_conteudo = QWidget()
        self.lista_layout = QVBoxLayout(self.lista_conteudo)
        self.lista_layout.setContentsMargins(0, 0, 0, 0)
        self.lista_layout.setSpacing(8)
        self.lista_layout.addStretch(1)
        self.lista_area.setWidget(self.lista_conteudo)
        caixa.addWidget(self.lista_area)
        return painel

    def _redesenhar_lista(self) -> None:
        while self.lista_layout.count() > 1:
            item = self.lista_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        clipes = self.servico.registro.da_sessao(self._inicio_da_sessao)
        if not clipes:
            vazio = QLabel("Nenhum clipe ainda. O que você criar aparece aqui.")
            vazio.setObjectName("Muted")
            self.lista_layout.insertWidget(0, vazio)
        else:
            for clipe in clipes:
                self.lista_layout.insertWidget(
                    self.lista_layout.count() - 1, self._linha_do_clipe(clipe)
                )
        self._atualizar_pauta()

    def _linha_do_clipe(self, clipe: Clipe) -> QWidget:
        linha = QWidget()
        caixa = QHBoxLayout(linha)
        caixa.setContentsMargins(0, 0, 0, 0)
        caixa.setSpacing(8)

        marca = "●" if clipe.confirmado else "○"
        rotulo = QLabel(f"{marca}  {clipe.horario}   {clipe.texto}")
        rotulo.setToolTip(
            "Pronto na Twitch." if clipe.confirmado else "Ainda processando na Twitch."
        )
        caixa.addWidget(rotulo, 1)

        assistir = QPushButton("Assistir")
        assistir.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(clipe.url)))
        caixa.addWidget(assistir)

        if clipe.edit_url:
            editar = QPushButton("Editar")
            editar.setToolTip("Ajustar o trecho e o título na Twitch.")
            editar.clicked.connect(
                lambda: QDesktopServices.openUrl(QUrl(clipe.edit_url))
            )
            caixa.addWidget(editar)

        usar = QPushButton("Usar" if clipe.usar is not True else "✔ Usar")
        usar.setCheckable(True)
        usar.setChecked(clipe.usar is True)
        usar.clicked.connect(lambda: self._decidir(clipe.id, True))
        caixa.addWidget(usar)

        descartar = QPushButton("Descartar")
        descartar.setCheckable(True)
        descartar.setChecked(clipe.usar is False)
        descartar.clicked.connect(lambda: self._decidir(clipe.id, False))
        caixa.addWidget(descartar)
        return linha

    def _decidir(self, clip_id: str, usar: bool) -> None:
        atual = next((c for c in self.servico.registro.itens if c.id == clip_id), None)
        # Clicar de novo no mesmo botao desfaz a escolha.
        novo = None if atual is not None and atual.usar is usar else usar
        self.servico.registro.decidir(clip_id, novo)
        self._redesenhar_lista()

    # ------------------------------------------------------------- pauta
    def _painel_pauta(self) -> QWidget:
        painel = NeonPanel(accent="#B9FF43")
        caixa = QVBoxLayout(painel)
        caixa.setContentsMargins(18, 16, 18, 16)
        caixa.setSpacing(10)

        titulo = QLabel("03  |  Pauta de cortes")
        titulo.setObjectName("Kicker")
        caixa.addWidget(titulo)

        explicacao = QLabel(
            "O que sobrou depois da triagem, pronto para colar onde você edita."
        )
        explicacao.setObjectName("Muted")
        explicacao.setWordWrap(True)
        caixa.addWidget(explicacao)

        self.campo_pauta = QPlainTextEdit()
        self.campo_pauta.setReadOnly(True)
        self.campo_pauta.setMinimumHeight(140)
        caixa.addWidget(self.campo_pauta)

        acoes = QHBoxLayout()
        copiar = QPushButton("Copiar")
        copiar.setObjectName("PrimaryButton")
        copiar.clicked.connect(
            lambda: QGuiApplication.clipboard().setText(self.campo_pauta.toPlainText())
        )
        acoes.addWidget(copiar)
        acoes.addStretch(1)
        caixa.addLayout(acoes)
        return painel

    def _atualizar_pauta(self) -> None:
        clipes = self.servico.registro.da_sessao(self._inicio_da_sessao)
        self.campo_pauta.setPlainText(self.servico.registro.para_pauta(clipes))

    # -------------------------------------------------------- encerramento
    def encerrar(self) -> None:
        self._relogio.stop()
        for worker in (self._clipe, self._estado, self._confirmacao):
            if worker is not None and worker.isRunning():
                worker.encerrar()
