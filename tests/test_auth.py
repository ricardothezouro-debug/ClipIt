"""O login por device code, sem rede e sem esperar 30 minutos."""
from __future__ import annotations

import json
import urllib.error

import pytest

from clipit.core import twitch_auth
from clipit.core.errors import Cancelado, ClipItError, PrecisaLogar
from clipit.core.twitch_auth import CodigoDeDispositivo, GuardaDeTokens, Tokens


def _erro(codigo: int, mensagem: str = "") -> urllib.error.HTTPError:
    import io
    corpo = json.dumps({"message": mensagem}).encode()
    return urllib.error.HTTPError("u", codigo, "erro", {}, io.BytesIO(corpo))


class _Respostas:
    """Devolve, em ordem, o que a Twitch responderia."""

    def __init__(self, *respostas) -> None:
        self.respostas = list(respostas)
        self.chamadas = 0

    def __call__(self, url, campos, timeout=30.0):
        self.chamadas += 1
        proxima = self.respostas.pop(0)
        if isinstance(proxima, Exception):
            raise proxima
        return proxima


def _codigo(**kwargs) -> CodigoDeDispositivo:
    base = dict(device_code="dc", user_code="WXYZ-4821",
                verification_uri="https://twitch.tv/activate",
                expires_in=1800, interval=5.0)
    base.update(kwargs)
    return CodigoDeDispositivo(**base)


def test_espera_enquanto_o_usuario_nao_autorizou(monkeypatch):
    """400 com authorization_pending e o caso NORMAL, nao um erro."""
    respostas = _Respostas(
        _erro(400, "authorization_pending"),
        _erro(400, "authorization_pending"),
        {"access_token": "AT", "refresh_token": "RT", "expires_in": 14400},
    )
    monkeypatch.setattr(twitch_auth, "_postar", respostas)

    relogio = [1000.0]
    tokens = twitch_auth.aguardar(
        "cid", _codigo(), cancelar=None,
        dormir=lambda s: relogio.__setitem__(0, relogio[0] + s),
        agora=lambda: relogio[0],
    )
    assert tokens.access_token == "AT"
    assert respostas.chamadas == 3


def test_slow_down_aumenta_o_intervalo(monkeypatch):
    """Insistir no mesmo ritmo depois de um slow_down seria piorar de propósito."""
    respostas = _Respostas(
        _erro(400, "slow down"),
        {"access_token": "AT", "refresh_token": "RT", "expires_in": 14400},
    )
    monkeypatch.setattr(twitch_auth, "_postar", respostas)
    codigo = _codigo(interval=5.0)
    relogio = [0.0]
    twitch_auth.aguardar(
        "cid", codigo,
        dormir=lambda s: relogio.__setitem__(0, relogio[0] + s),
        agora=lambda: relogio[0],
    )
    assert codigo.interval == 10.0


def test_codigo_expirado_vira_erro_claro(monkeypatch):
    monkeypatch.setattr(twitch_auth, "_postar", _Respostas(_erro(400, "pending")))
    relogio = [0.0]
    with pytest.raises(ClipItError) as info:
        twitch_auth.aguardar(
            "cid", _codigo(expires_in=1),
            dormir=lambda s: relogio.__setitem__(0, relogio[0] + 100),
            agora=lambda: relogio[0],
        )
    assert "expirou" in info.value.titulo.lower()


def test_cancelar_interrompe_a_espera(monkeypatch):
    monkeypatch.setattr(twitch_auth, "_postar", _Respostas())
    with pytest.raises(Cancelado):
        twitch_auth.aguardar(
            "cid", _codigo(), cancelar=lambda: True,
            dormir=lambda s: None, agora=lambda: 0.0,
        )


def test_renovar_devolve_o_refresh_novo(monkeypatch):
    """O refresh da Twitch e de USO UNICO: guardar o antigo perde o acesso."""
    monkeypatch.setattr(twitch_auth, "_postar", _Respostas(
        {"access_token": "AT2", "refresh_token": "RT2", "expires_in": 14400}
    ))
    tokens = twitch_auth.renovar("cid", "RT1", agora=lambda: 0.0)
    assert tokens.refresh_token == "RT2"
    assert tokens.expira_em == 14400


def test_renovar_sem_token_pede_login():
    with pytest.raises(PrecisaLogar):
        twitch_auth.renovar("cid", "")


def test_refresh_recusado_pede_login_em_vez_de_erro_cru(monkeypatch):
    monkeypatch.setattr(twitch_auth, "_postar", _Respostas(_erro(400, "invalid")))
    with pytest.raises(PrecisaLogar):
        twitch_auth.renovar("cid", "RT")


def test_token_vencido_tem_margem():
    """Renovar 60s antes evita o token morrer no meio de um clipe."""
    import time
    assert Tokens("AT", "RT", time.time() + 30).vencido is True
    assert Tokens("AT", "RT", time.time() + 600).vencido is False


def test_guarda_salva_le_e_esquece(tmp_path):
    guarda = GuardaDeTokens(tmp_path / "tokens.json")
    assert guarda.carregar() is None

    guarda.salvar(Tokens("AT", "RT", 123.0))
    lido = guarda.carregar()
    assert (lido.access_token, lido.refresh_token) == ("AT", "RT")

    guarda.esquecer()
    assert guarda.carregar() is None


def test_guarda_nao_deixa_o_arquivo_legivel_por_outros(tmp_path):
    import sys
    if sys.platform == "win32":
        return  # o chmod do POSIX nao se aplica; o arquivo ja esta no perfil
    caminho = tmp_path / "tokens.json"
    GuardaDeTokens(caminho).salvar(Tokens("AT", "RT", 1.0))
    assert oct(caminho.stat().st_mode)[-3:] == "600"


def test_arquivo_corrompido_nao_derruba_o_plugin(tmp_path):
    caminho = tmp_path / "tokens.json"
    caminho.write_text("{isso nao e json", encoding="utf-8")
    assert GuardaDeTokens(caminho).carregar() is None
