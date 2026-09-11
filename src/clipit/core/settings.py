"""Preferencias do plugin. Nunca guarda credencial -- isso e do tokens.json."""
from __future__ import annotations

import json
from typing import Any

from clipit.core.paths import settings_path

PADRAO: dict[str, Any] = {
    # Vem do app que o usuario registra em dev.twitch.tv/console. E publico por
    # natureza (aparece em qualquer requisicao), mas e de cada um.
    "client_id": "",
    # False = clipa o momento do BROADCAST (o que voce acabou de fazer).
    "com_delay": False,
    # Segundos entre clipes. Protege de apertar tres vezes e gerar tres clipes
    # iguais -- e de bater no limite da Twitch a toa.
    "intervalo_minimo": 15,
    # Escrever a marcacao (com o link) no arquivo do Marcador do Sidekick.
    "escrever_no_marcador": True,
    "texto_padrao": "clipe",
}


class Settings:
    def __init__(self, caminho=None) -> None:
        self.path = caminho or settings_path()
        self._dados = self._carregar()

    def _carregar(self) -> dict[str, Any]:
        dados = dict(PADRAO)
        try:
            existente = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return dados
        if isinstance(existente, dict):
            # Preserva chaves desconhecidas: se uma versao futura acrescentar um
            # campo e o usuario voltar para esta, o campo nao e apagado.
            dados.update(existente)
        return dados

    def get(self, chave: str, padrao: Any = None) -> Any:
        return self._dados.get(chave, padrao if padrao is not None else PADRAO.get(chave))

    def set(self, chave: str, valor: Any) -> None:
        self._dados[chave] = valor
        self.salvar()

    def salvar(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self._dados, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except OSError:
            pass

    @property
    def client_id(self) -> str:
        return str(self._dados.get("client_id", "")).strip()
