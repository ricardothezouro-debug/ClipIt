"""Gera o icone do ClipIt: 256x256, fundo transparente.

Segue o §5 do PLUGIN_STANDARD: traco neon em gradiente ciano→magenta sobre um
quadrado arredondado escuro, como o StreamOn. A cor da Twitch NAO entra aqui --
ela fica no accent do card. Um icone na cor de um servico de terceiro faz o
plugin parecer um app de fora dentro do hub.

Desenhado por codigo para nao depender de fonte nem de arquivo externo.

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
# Paleta do design system (PLUGIN_STANDARD §6).
VOID_BLACK = QColor("#0A0B12")
BORDER = QColor("#273140")
ELECTRIC_CYAN = QColor("#37F2FF")
NEON_MAGENTA = QColor("#FF4FD8")


def _neon(a: QPointF, b: QPointF) -> QLinearGradient:
    g = QLinearGradient(a, b)
    g.setColorAt(0.0, ELECTRIC_CYAN)
    g.setColorAt(1.0, NEON_MAGENTA)
    return g


def _caneta(largura: float, a: QPointF, b: QPointF) -> QPen:
    caneta = QPen(QBrush(_neon(a, b)), largura)
    caneta.setCapStyle(Qt.PenCapStyle.RoundCap)
    caneta.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return caneta


def desenhar(imagem: QImage) -> None:
    p = QPainter(imagem)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Fundo: quadrado arredondado escuro com a borda do sistema.
    fundo = QRectF(14, 14, TAMANHO - 28, TAMANHO - 28)
    p.setPen(QPen(BORDER, 6))
    p.setBrush(VOID_BLACK)
    p.drawRoundedRect(fundo, 54, 54)

    # Um brilho suave atras do glifo, para o neon "acender".
    brilho = QRectF(64, 74, 128, 112)
    halo = QBrush(QColor(55, 242, 255, 22))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(halo)
    p.drawRoundedRect(brilho.adjusted(-18, -18, 18, 18), 40, 40)

    inicio, fim = QPointF(58, 60), QPointF(198, 200)

    # A claquete, em traco: a tampa inclinada...
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(_caneta(11, inicio, fim))
    p.save()
    p.translate(62, 86)
    p.rotate(-12)
    tampa = QPainterPath()
    tampa.addRoundedRect(QRectF(0, -22, 138, 26), 6, 6)
    p.drawPath(tampa)
    # ...com as listras diagonais dentro dela...
    p.setPen(_caneta(7, inicio, fim))
    for i in range(3):
        x = 26 + i * 40
        p.drawLine(QPointF(x, -18), QPointF(x - 12, 0))
    p.restore()

    # ...e o corpo.
    p.setPen(_caneta(11, inicio, fim))
    corpo = QPainterPath()
    corpo.addRoundedRect(QRectF(62, 100, 134, 88), 12, 12)
    p.drawPath(corpo)

    # O "play" -- e clipe, afinal -- preenchido com o mesmo neon.
    play = QPolygonF([QPointF(114, 122), QPointF(114, 166), QPointF(154, 144)])
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(_neon(QPointF(114, 122), QPointF(154, 166))))
    p.drawPolygon(play)

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
