"""O que acontece quando voce aperta o atalho.

Junta as pecas numa ordem que importa:

1. garante um access token valido (renovando e **gravando o novo antes de
   qualquer outra coisa**, porque o refresh da Twitch e de uso unico);
2. respeita o intervalo minimo, para tres toques nao virarem tres clipes;
3. cria o clipe;
4. registra e escreve a marcacao -- ja com o link.

O link nao espera o processamento: `https://clips.twitch.tv/<id>` sai do id que
o POST devolve na hora. Os ~15s de processamento decidem quando o clipe ABRE,
nao quando o link existe. Por isso a marcacao nasce completa em vez de ficar
pela metade esperando.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

from clipit.core import marcador, twitch_auth
from clipit.core.clips import Clipe, RegistroDeClipes
from clipit.core.errors import ClipItError, PrecisaLogar
from clipit.core.settings import Settings
from clipit.core.twitch_api import TwitchAPI, Usuario


@dataclass
class Resultado:
    clipe: Clipe
    escreveu_no_marcador: bool


class CedoDemais(ClipItError):
    def __init__(self, faltam: float) -> None:
        super().__init__(
            "Espere um instante",
            f"O último clipe foi há pouco; faltam {int(faltam) + 1}s.",
            "Isso evita clipes repetidos do mesmo momento.",
        )
        self.faltam = faltam


class ClipItService:
    def __init__(
        self,
        settings: Settings,
        guarda: twitch_auth.GuardaDeTokens,
        registro: Optional[RegistroDeClipes] = None,
        agora: Callable[[], float] = time.monotonic,
    ) -> None:
        self.settings = settings
        self.guarda = guarda
        self.registro = registro or RegistroDeClipes()
        self._agora = agora
        self._ultimo_clipe = 0.0
        self._usuario: Optional[Usuario] = None

    # --- credencial --------------------------------------------------------
    def conectado(self) -> bool:
        return self.guarda.carregar() is not None

    def _token(self) -> str:
        tokens = self.guarda.carregar()
        if tokens is None:
            raise PrecisaLogar()
        if tokens.vencido:
            novos = twitch_auth.renovar(self.settings.client_id, tokens.refresh_token)
            # GRAVAR ANTES de usar: a Twitch ja invalidou o refresh antigo, e
            # um erro daqui para frente deixaria o usuario sem nenhum valido.
            self.guarda.salvar(novos)
            return novos.access_token
        return tokens.access_token

    def api(self) -> TwitchAPI:
        return TwitchAPI(self.settings.client_id, self._token)

    def usuario(self, recarregar: bool = False) -> Usuario:
        if self._usuario is None or recarregar:
            self._usuario = self.api().usuario_atual()
        return self._usuario

    def desconectar(self) -> None:
        self.guarda.esquecer()
        self._usuario = None

    # --- o clipe -----------------------------------------------------------
    def segundos_ate_poder(self) -> float:
        intervalo = float(self.settings.get("intervalo_minimo", 15))
        passou = self._agora() - self._ultimo_clipe
        return max(0.0, intervalo - passou)

    def clipar(self, texto: str = "", quando: Optional[datetime] = None) -> Resultado:
        faltam = self.segundos_ate_poder()
        if self._ultimo_clipe and faltam > 0:
            raise CedoDemais(faltam)

        usuario = self.usuario()
        criado = self.api().criar_clipe(
            usuario.id, com_delay=bool(self.settings.get("com_delay", False))
        )
        self._ultimo_clipe = self._agora()

        momento = quando or datetime.now()
        rotulo = " ".join((texto or "").split()) or str(
            self.settings.get("texto_padrao", "clipe")
        )
        clipe = self.registro.adicionar(Clipe(
            id=criado.id,
            url=criado.url,
            edit_url=criado.edit_url,
            texto=rotulo,
            quando=momento.isoformat(timespec="seconds"),
        ))

        escreveu = False
        if self.settings.get("escrever_no_marcador", True):
            escreveu = marcador.registrar(rotulo, criado.url, momento)

        return Resultado(clipe=clipe, escreveu_no_marcador=escreveu)

    def confirmar(self, clip_id: str) -> bool:
        """Pergunta a Twitch se o clipe terminou de processar."""
        if self.api().clipe_pronto(clip_id) is None:
            return False
        self.registro.marcar_confirmado(clip_id)
        return True
