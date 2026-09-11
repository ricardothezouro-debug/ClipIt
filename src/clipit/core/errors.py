"""Erros que a interface sabe mostrar.

Tres campos e so: titulo (uma linha), detalhe (o que aconteceu) e acao (o que
o usuario pode fazer). A UI nunca inventa texto -- le esses tres.
"""
from __future__ import annotations


class ClipItError(Exception):
    def __init__(self, titulo: str, detalhe: str = "", acao: str = "") -> None:
        super().__init__(f"{titulo}. {detalhe}".strip())
        self.titulo = titulo
        self.detalhe = detalhe
        self.acao = acao


class PrecisaLogar(ClipItError):
    def __init__(self, detalhe: str = "") -> None:
        super().__init__(
            "Conecte sua conta da Twitch",
            detalhe or "O acesso expirou ou ainda não foi autorizado.",
            "Abra Configurações e conecte de novo.",
        )


class NaoEstaAoVivo(ClipItError):
    def __init__(self) -> None:
        super().__init__(
            "Você não está ao vivo",
            "A Twitch só cria clipes durante a transmissão.",
            "Comece a live e tente de novo.",
        )


class Cancelado(ClipItError):
    def __init__(self) -> None:
        super().__init__("Cancelado", "", "")


class LimiteDeUso(ClipItError):
    def __init__(self, esperar: float = 60.0) -> None:
        super().__init__(
            "A Twitch pediu para esperar",
            f"Limite de requisições atingido; liberando em ~{int(esperar)}s.",
            "Espere um pouco antes de clipar de novo.",
        )
        self.esperar = esperar
