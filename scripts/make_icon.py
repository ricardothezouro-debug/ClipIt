"""Gera o icone do ClipIt: 256x256, fundo transparente.

Um claquete estilizado no roxo da Twitch, com o "play" branco e uma linha de
corte. Desenhado por codigo para nao depender de fonte nem de arquivo externo.

    PYTHONPATH=src python scripts/make_icon.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)

TAMANHO = 256
ROXO = QColor("#9146FF")
ROXO_ESCURO = QColor("#5C16C5")
BRANCO = QColor("#FFFFFF")
CIANO = QColor("#37F2FF")


def desenhar(imagem: QImage) -> None:
    p = QPainter(imagem)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Fundo: quadrado arredondado com degrade roxo.
    fundo = QRectF(16, 16, TAMANHO - 32, TAMANHO - 32)
    degrade = QLinearGradient(fundo.topLeft(), fundo.bottomRight())
    degrade.setColorAt(0.0, ROXO)
    degrade.setColorAt(1.0, ROXO_ESCURO)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(degrade))
    p.drawRoundedRect(fundo, 56, 56)

    # A tampa do claquete: uma faixa listrada no topo, inclinada.
    p.save()
    p.translate(52, 78)
    p.rotate(-14)
    tampa = QRectF(0, -22, 168, 30)
    p.setBrush(BRANCO)
    p.drawRoundedRect(tampa, 8, 8)
    p.setBrush(ROXO_ESCURO)
    for i in range(4):
        listra = QPolygonF([
            QPointF(18 + i * 40, -22), QPointF(38 + i * 40, -22),
            QPointF(26 + i * 40, 8), QPointF(6 + i * 40, 8),
        ])
        p.drawPolygon(listra)
    p.restore()

    # O corpo do claquete.
    corpo = QRectF(52, 92, 152, 104)
    p.setBrush(BRANCO)
    p.drawRoundedRect(corpo, 12, 12)

    # O "play" -- e clipe, afinal.
    play = QPolygonF([QPointF(112, 118), QPointF(112, 170), QPointF(158, 144)])
    p.setBrush(ROXO)
    p.drawPolygon(play)

    # A linha de corte, tracejada, em ciano: e o "It" do ClipIt.
    caneta = QPen(CIANO, 7, Qt.PenStyle.CustomDashLine, Qt.PenCapStyle.RoundCap)
    caneta.setDashPattern([2.2, 2.2])
    p.setPen(caneta)
    p.drawLine(QPointF(40, 214), QPointF(216, 214))
    p.end()


def main() -> int:
    QGuiApplication(sys.argv)
    imagem = QImage(TAMANHO, TAMANHO, QImage.Format.Format_ARGB32)
    imagem.fill(Qt.GlobalColor.transparent)
    desenhar(imagem)
    destino = Path(__file__).resolve().parent.parent / "src/clipit/assets/brand/app_icon.png"
    destino.parent.mkdir(parents=True, exist_ok=True)
    imagem.save(str(destino))
    print(f"icone salvo em {destino} ({imagem.width()}x{imagem.height()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
