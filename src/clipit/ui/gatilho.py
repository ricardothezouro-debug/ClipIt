"""A ponte entre a thread do atalho e a thread da GUI.

O backend de hotkeys chama o callback na thread dele. Emitir um Signal de um
QObject e o jeito seguro de atravessar: o Qt enfileira a entrega para a thread
do receptor, e o slot roda na GUI.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class Gatilho(QObject):
    disparou = Signal()

    def callback(self) -> None:
        """E isto que o backend chama, de fora da GUI."""
        self.disparou.emit()
