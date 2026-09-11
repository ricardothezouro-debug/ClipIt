"""Login na Twitch pelo Device Code Grant Flow.

POR QUE ESTE FLUXO E NAO OUTRO: o plugin mora num repositorio publico. O fluxo
de Authorization Code exigiria um `client_secret`, que viraria publico no
primeiro push -- e um segredo publicado nao e segredo. O Device Code nao usa
secret para clientes publicos: o app mostra um codigo curto, o usuario digita
em twitch.tv/activate, e pronto. E o mesmo caminho que uma smart TV usa.

ARMADILHA QUE JA CUSTOU CONTA DE GENTE: o refresh token da Twitch e de **uso
unico**. Cada renovacao devolve um novo e invalida o anterior. Se o novo nao for
gravado antes de qualquer outra coisa poder falhar, o usuario perde o acesso e
precisa logar de novo sem entender por que.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from clipit.core.errors import Cancelado, ClipItError, PrecisaLogar
from clipit.core.netcompat import urlopen

URL_DEVICE = "https://id.twitch.tv/oauth2/device"
URL_TOKEN = "https://id.twitch.tv/oauth2/token"

#: `clips:edit` cria clipes. Nao pedimos mais nada: ler o proprio usuario e
#: saber se a live esta no ar nao exigem escopo.
ESCOPOS = "clips:edit"

#: Piso de seguranca para o intervalo de polling, caso a Twitch mande 0.
INTERVALO_MINIMO = 5.0


@dataclass
class CodigoDeDispositivo:
    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: float


@dataclass
class Tokens:
    access_token: str
    refresh_token: str
    #: Instante (epoch) em que o access token deixa de valer.
    expira_em: float

    @property
    def vencido(self) -> bool:
        # Margem de 60s: melhor renovar cedo do que falhar no meio de um clipe.
        return time.time() >= self.expira_em - 60


def _postar(url: str, campos: dict, timeout: float = 30.0) -> dict:
    corpo = urllib.parse.urlencode(campos).encode()
    pedido = urllib.request.Request(
        url, data=corpo,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urlopen(pedido, timeout=timeout) as resposta:
        return json.load(resposta)


def _erro_do_corpo(erro: urllib.error.HTTPError) -> str:
    try:
        return str(json.loads(erro.read().decode("utf-8")).get("message", ""))
    except Exception:
        return ""


def iniciar(client_id: str, escopos: str = ESCOPOS) -> CodigoDeDispositivo:
    """Pede a Twitch o codigo que o usuario vai digitar no navegador."""
    if not client_id:
        raise ClipItError(
            "Falta o Client ID",
            "O ClipIt precisa de um aplicativo registrado na sua conta de "
            "desenvolvedor da Twitch.",
            "Abra Configurações — tem um passo a passo lá.",
        )
    try:
        dados = _postar(URL_DEVICE, {"client_id": client_id, "scopes": escopos})
    except urllib.error.HTTPError as e:
        raise ClipItError(
            "A Twitch recusou o pedido de login",
            _erro_do_corpo(e) or f"HTTP {e.code}",
            "Confira se o Client ID está correto.",
        ) from e

    return CodigoDeDispositivo(
        device_code=dados["device_code"],
        user_code=dados["user_code"],
        verification_uri=dados.get("verification_uri", "https://www.twitch.tv/activate"),
        expires_in=int(dados.get("expires_in", 1800)),
        interval=max(float(dados.get("interval", 5)), INTERVALO_MINIMO),
    )


def aguardar(
    client_id: str,
    codigo: CodigoDeDispositivo,
    escopos: str = ESCOPOS,
    cancelar: Optional[Callable[[], bool]] = None,
    dormir: Callable[[float], None] = time.sleep,
    agora: Callable[[], float] = time.time,
) -> Tokens:
    """Pergunta a Twitch, de tempos em tempos, se o usuario ja autorizou.

    `dormir` e `agora` sao injetaveis para o teste nao levar 30 minutos.
    """
    limite = agora() + codigo.expires_in
    while True:
        if cancelar and cancelar():
            raise Cancelado()
        if agora() >= limite:
            raise ClipItError(
                "O código expirou",
                "Ninguém autorizou dentro do tempo.",
                "Gere um código novo.",
            )
        dormir(codigo.interval)
        if cancelar and cancelar():
            raise Cancelado()
        try:
            dados = _postar(URL_TOKEN, {
                "client_id": client_id,
                "device_code": codigo.device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "scopes": escopos,
            })
        except urllib.error.HTTPError as e:
            # 400 com authorization_pending e o caso NORMAL: o usuario ainda
            # nao terminou. Qualquer outro 4xx e erro de verdade.
            mensagem = _erro_do_corpo(e).lower()
            if e.code == 400 and ("pending" in mensagem or not mensagem):
                continue
            if e.code == 400 and "slow down" in mensagem:
                codigo.interval += 5
                continue
            raise ClipItError(
                "A Twitch recusou a autorização",
                _erro_do_corpo(e) or f"HTTP {e.code}",
                "Tente conectar de novo.",
            ) from e

        return Tokens(
            access_token=dados["access_token"],
            refresh_token=dados.get("refresh_token", ""),
            expira_em=agora() + float(dados.get("expires_in", 14400)),
        )


def renovar(client_id: str, refresh_token: str,
            agora: Callable[[], float] = time.time) -> Tokens:
    """Troca o refresh token por um par novo. O antigo morre nesta chamada."""
    if not refresh_token:
        raise PrecisaLogar("Nunca houve um login nesta máquina.")
    try:
        dados = _postar(URL_TOKEN, {
            "client_id": client_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        })
    except urllib.error.HTTPError as e:
        if e.code in (400, 401):
            raise PrecisaLogar(
                "O acesso salvo não vale mais (expirou ou foi revogado)."
            ) from e
        raise ClipItError(
            "Não consegui renovar o acesso",
            _erro_do_corpo(e) or f"HTTP {e.code}",
            "Tente conectar de novo.",
        ) from e

    return Tokens(
        access_token=dados["access_token"],
        refresh_token=dados.get("refresh_token", refresh_token),
        expira_em=agora() + float(dados.get("expires_in", 14400)),
    )


class GuardaDeTokens:
    """Le e grava os tokens em disco, com a permissao apertada."""

    def __init__(self, caminho: Path) -> None:
        self.caminho = Path(caminho)

    def carregar(self) -> Optional[Tokens]:
        try:
            dados = json.loads(self.caminho.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        try:
            return Tokens(
                access_token=str(dados["access_token"]),
                refresh_token=str(dados.get("refresh_token", "")),
                expira_em=float(dados.get("expira_em", 0.0)),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def salvar(self, tokens: Tokens) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        # Grava em arquivo temporario e troca: se faltar energia no meio, o
        # arquivo bom continua la em vez de virar metade de um JSON.
        temporario = self.caminho.with_suffix(".tmp")
        temporario.write_text(json.dumps({
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "expira_em": tokens.expira_em,
        }), encoding="utf-8")
        self._apertar(temporario)
        temporario.replace(self.caminho)
        self._apertar(self.caminho)

    def esquecer(self) -> None:
        self.caminho.unlink(missing_ok=True)

    @staticmethod
    def _apertar(caminho: Path) -> None:
        """So o dono le. No Windows o chmod nao faz nada -- e tudo bem, o
        arquivo ja esta no perfil do usuario."""
        try:
            caminho.chmod(0o600)
        except OSError:
            pass
