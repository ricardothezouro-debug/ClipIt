"""As chamadas da Helix que o ClipIt usa. So leitura, e um POST para clipar.

O que a API permite e o que NAO permite, ja que isso define o produto:

* `POST /helix/clips` aceita **broadcaster_id** e **has_delay**, e mais nada.
  Nao existe parametro de duracao: a Twitch escolhe a janela (~30s do que
  acabou de passar) e devolve um `edit_url` para ajustar depois, na mao.
* Nao da para definir o titulo na criacao. O clipe nasce com o nome padrao; o
  texto do usuario fica na marcacao local, nao no clipe publico.
* O clipe leva ate ~15s para processar. Ate la, `GET /helix/clips?id=` devolve
  lista vazia -- isso NAO e erro, e "ainda esta pronto".
* So funciona com a transmissao no ar.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

from clipit.core.errors import ClipItError, LimiteDeUso, NaoEstaAoVivo, PrecisaLogar
from clipit.core.netcompat import urlopen

BASE = "https://api.twitch.tv/helix"


@dataclass
class Usuario:
    id: str
    login: str
    nome: str


@dataclass
class ClipeCriado:
    id: str
    edit_url: str

    @property
    def url(self) -> str:
        """O link de assistir, derivavel do id sem esperar o processamento."""
        return f"https://clips.twitch.tv/{self.id}"


class TwitchAPI:
    """Cliente fino da Helix.

    Recebe uma funcao que devolve um access token valido, em vez do token: quem
    sabe renovar e o chamador, e assim uma renovacao no meio do caminho nao
    precisa reconstruir este objeto.
    """

    def __init__(self, client_id: str, dar_token: Callable[[], str]) -> None:
        self.client_id = client_id
        self._dar_token = dar_token

    # --- transporte --------------------------------------------------------
    def _chamar(self, metodo: str, caminho: str, parametros: Optional[dict] = None,
                _repetir: bool = True) -> dict:
        url = f"{BASE}{caminho}"
        if parametros:
            url = f"{url}?{urllib.parse.urlencode(parametros)}"
        pedido = urllib.request.Request(url, method=metodo, headers={
            "Client-Id": self.client_id,
            "Authorization": f"Bearer {self._dar_token()}",
        })
        try:
            with urlopen(pedido, timeout=30) as resposta:
                corpo = resposta.read().decode("utf-8")
            return json.loads(corpo) if corpo else {}
        except urllib.error.HTTPError as e:
            return self._traduzir(e, metodo, caminho, parametros, _repetir)

    def _traduzir(self, erro, metodo, caminho, parametros, repetir) -> dict:
        if erro.code == 401 and repetir:
            # O token pode ter vencido entre o cheque e a chamada. Uma segunda
            # tentativa pega o token renovado por `dar_token`.
            return self._chamar(metodo, caminho, parametros, _repetir=False)
        if erro.code == 401:
            raise PrecisaLogar("A Twitch recusou o acesso salvo.") from erro
        if erro.code == 429:
            espera = erro.headers.get("Ratelimit-Reset")
            try:
                import time
                segundos = max(1.0, float(espera) - time.time()) if espera else 60.0
            except (TypeError, ValueError):
                segundos = 60.0
            raise LimiteDeUso(segundos) from erro

        detalhe = ""
        try:
            detalhe = str(json.loads(erro.read().decode("utf-8")).get("message", ""))
        except Exception:
            pass
        raise ClipItError(
            "A Twitch recusou a chamada",
            detalhe or f"HTTP {erro.code}",
            "Tente de novo em alguns segundos.",
        ) from erro

    # --- consultas ---------------------------------------------------------
    def usuario_atual(self) -> Usuario:
        dados = self._chamar("GET", "/users").get("data") or []
        if not dados:
            raise PrecisaLogar("A Twitch não devolveu nenhum usuário.")
        u = dados[0]
        return Usuario(
            id=str(u.get("id", "")),
            login=str(u.get("login", "")),
            nome=str(u.get("display_name") or u.get("login", "")),
        )

    def esta_ao_vivo(self, broadcaster_id: str) -> bool:
        dados = self._chamar("GET", "/streams", {"user_id": broadcaster_id})
        return bool(dados.get("data"))

    # --- o que interessa ---------------------------------------------------
    def criar_clipe(self, broadcaster_id: str, com_delay: bool = False) -> ClipeCriado:
        """Clipa o que acabou de passar.

        `com_delay=False` pega o momento do BROADCAST -- o que voce acabou de
        fazer no jogo. `True` alinha com o que o espectador esta vendo, uns 15s
        atras. Qual dos dois serve depende do gatilho: reagir ao jogo pede
        False; reagir ao chat reagindo pede True.
        """
        try:
            dados = self._chamar("POST", "/clips", {
                "broadcaster_id": broadcaster_id,
                "has_delay": "true" if com_delay else "false",
            })
        except ClipItError as e:
            # A Twitch devolve 404 quando nao ha transmissao no ar. Traduzir
            # para algo que o usuario entenda, em vez de "HTTP 404".
            if "404" in (e.detalhe or "") or "offline" in (e.detalhe or "").lower():
                raise NaoEstaAoVivo() from e
            raise

        itens = dados.get("data") or []
        if not itens:
            raise ClipItError(
                "A Twitch não devolveu o clipe",
                "A chamada passou, mas veio sem dados.",
                "Tente de novo.",
            )
        return ClipeCriado(
            id=str(itens[0].get("id", "")),
            edit_url=str(itens[0].get("edit_url", "")),
        )

    def clipe_pronto(self, clip_id: str) -> Optional[dict]:
        """None enquanto processa. Nao e erro -- e so ainda nao estar pronto."""
        itens = self._chamar("GET", "/clips", {"id": clip_id}).get("data") or []
        return itens[0] if itens else None
