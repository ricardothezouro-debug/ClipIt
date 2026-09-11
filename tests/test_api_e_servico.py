"""A camada da Twitch e a orquestracao, sem tocar na rede."""
from __future__ import annotations

import io
import json
import urllib.error
from datetime import datetime

import pytest

from clipit.core import marcador, service as service_mod, twitch_api
from clipit.core.clips import Clipe, RegistroDeClipes
from clipit.core.errors import LimiteDeUso, NaoEstaAoVivo, PrecisaLogar
from clipit.core.service import CedoDemais, ClipItService
from clipit.core.settings import Settings
from clipit.core.twitch_api import TwitchAPI
from clipit.core.twitch_auth import GuardaDeTokens, Tokens


class _Resposta(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


def _http(codigo: int, mensagem: str = "", headers=None):
    return urllib.error.HTTPError(
        "u", codigo, "erro", headers or {},
        io.BytesIO(json.dumps({"message": mensagem}).encode()),
    )


class _Rede:
    """Responde no lugar do urlopen, guardando o que foi pedido."""

    def __init__(self, *respostas) -> None:
        self.respostas = list(respostas)
        self.pedidos = []

    def __call__(self, pedido, timeout=30):
        self.pedidos.append(pedido)
        proxima = self.respostas.pop(0) if self.respostas else {}
        if isinstance(proxima, Exception):
            raise proxima
        return _Resposta(json.dumps(proxima).encode())


def _api(monkeypatch, *respostas) -> tuple[TwitchAPI, _Rede]:
    rede = _Rede(*respostas)
    monkeypatch.setattr(twitch_api, "urlopen", rede)
    return TwitchAPI("cid", lambda: "AT"), rede


# --- a API ------------------------------------------------------------------


def test_criar_clipe_manda_broadcaster_e_delay(monkeypatch):
    api, rede = _api(monkeypatch, {"data": [{"id": "AbcXyz", "edit_url": "https://e/"}]})
    clipe = api.criar_clipe("123", com_delay=True)

    assert clipe.id == "AbcXyz"
    assert clipe.url == "https://clips.twitch.tv/AbcXyz"
    url = rede.pedidos[0].full_url
    assert "broadcaster_id=123" in url
    assert "has_delay=true" in url
    assert rede.pedidos[0].get_method() == "POST"


def test_o_link_nao_espera_o_processamento(monkeypatch):
    """O id volta no POST; a URL sai dele. Os ~15s decidem quando o clipe ABRE,
    nao quando o link existe -- por isso a marcacao ja nasce completa."""
    api, _ = _api(monkeypatch, {"data": [{"id": "Zzz", "edit_url": ""}]})
    assert api.criar_clipe("1").url.endswith("/Zzz")


def test_offline_vira_mensagem_de_gente(monkeypatch):
    api, _ = _api(monkeypatch, _http(404, "offline"))
    with pytest.raises(NaoEstaAoVivo):
        api.criar_clipe("123")


def test_limite_traz_quanto_esperar(monkeypatch):
    import time
    api, _ = _api(monkeypatch, _http(
        429, "too many", {"Ratelimit-Reset": str(int(time.time()) + 30)}
    ))
    with pytest.raises(LimiteDeUso) as info:
        api.criar_clipe("123")
    assert 0 < info.value.esperar <= 31


def test_401_tenta_de_novo_uma_vez_e_depois_pede_login(monkeypatch):
    """O token pode vencer entre o cheque e a chamada."""
    api, rede = _api(monkeypatch, _http(401), _http(401))
    with pytest.raises(PrecisaLogar):
        api.usuario_atual()
    assert len(rede.pedidos) == 2, "devia ter tentado de novo antes de desistir"


def test_clipe_ainda_processando_nao_e_erro(monkeypatch):
    api, _ = _api(monkeypatch, {"data": []})
    assert api.clipe_pronto("Abc") is None


def test_esta_ao_vivo(monkeypatch):
    api, _ = _api(monkeypatch, {"data": [{"id": "s"}]})
    assert api.esta_ao_vivo("1") is True


# --- o servico --------------------------------------------------------------


@pytest.fixture
def servico(tmp_path, monkeypatch) -> ClipItService:
    ajustes = Settings(tmp_path / "settings.json")
    ajustes.set("client_id", "cid")
    ajustes.set("intervalo_minimo", 15)
    guarda = GuardaDeTokens(tmp_path / "tokens.json")
    guarda.salvar(Tokens("AT", "RT", 9e12))
    registro = RegistroDeClipes(tmp_path / "clips.json")
    relogio = [1000.0]
    s = ClipItService(ajustes, guarda, registro, agora=lambda: relogio[0])
    s._relogio = relogio
    monkeypatch.setattr(marcador, "arquivo_ativo", lambda: None)
    return s


def _responde(monkeypatch, *respostas):
    rede = _Rede(*respostas)
    monkeypatch.setattr(twitch_api, "urlopen", rede)
    return rede


def test_clipar_registra_e_devolve_o_link(servico, monkeypatch):
    _responde(monkeypatch,
              {"data": [{"id": "1", "login": "gamox", "display_name": "Gamox"}]},
              {"data": [{"id": "AbcXyz", "edit_url": "https://e/"}]})

    resultado = servico.clipar("engraçado")

    assert resultado.clipe.url == "https://clips.twitch.tv/AbcXyz"
    assert resultado.clipe.texto == "engraçado"
    assert servico.registro.itens[-1].id == "AbcXyz"


def test_tres_toques_seguidos_nao_viram_tres_clipes(servico, monkeypatch):
    """Sem isso, segurar a tecla gera clipes identicos e queima o limite."""
    _responde(monkeypatch,
              {"data": [{"id": "1", "login": "g", "display_name": "G"}]},
              {"data": [{"id": "A", "edit_url": ""}]})
    servico.clipar("um")

    with pytest.raises(CedoDemais) as info:
        servico.clipar("dois")
    assert info.value.faltam > 0


def test_depois_do_intervalo_pode_de_novo(servico, monkeypatch):
    _responde(monkeypatch,
              {"data": [{"id": "1", "login": "g", "display_name": "G"}]},
              {"data": [{"id": "A", "edit_url": ""}]},
              {"data": [{"id": "B", "edit_url": ""}]})
    servico.clipar("um")
    servico._relogio[0] += 20
    assert servico.clipar("dois").clipe.id == "B"


def test_sem_texto_usa_o_padrao(servico, monkeypatch):
    _responde(monkeypatch,
              {"data": [{"id": "1", "login": "g", "display_name": "G"}]},
              {"data": [{"id": "A", "edit_url": ""}]})
    assert servico.clipar("").clipe.texto == "clipe"


def test_token_vencido_e_renovado_e_gravado_antes_de_usar(servico, monkeypatch):
    """O refresh e de uso unico: se o novo nao for gravado primeiro, um erro
    depois deixaria o usuario sem nenhum token valido."""
    servico.guarda.salvar(Tokens("velho", "RT1", 0.0))  # ja vencido
    monkeypatch.setattr(
        service_mod.twitch_auth, "renovar",
        lambda cid, rt, **k: Tokens("AT2", "RT2", 9e12),
    )
    assert servico._token() == "AT2"
    assert servico.guarda.carregar().refresh_token == "RT2"


def test_sem_login_avisa_em_vez_de_estourar(servico):
    servico.desconectar()
    with pytest.raises(PrecisaLogar):
        servico._token()


def test_escreve_no_marcador_quando_ha_arquivo(servico, monkeypatch, tmp_path):
    alvo = tmp_path / "wolong.txt"
    alvo.write_text("", encoding="utf-8")
    monkeypatch.setattr(marcador, "arquivo_ativo", lambda: alvo)
    _responde(monkeypatch,
              {"data": [{"id": "1", "login": "g", "display_name": "G"}]},
              {"data": [{"id": "AbcXyz", "edit_url": ""}]})

    resultado = servico.clipar("morri", quando=datetime(2026, 9, 11, 16, 48, 3))

    assert resultado.escreveu_no_marcador is True
    assert alvo.read_text(encoding="utf-8") == (
        "[2026-09-11 16:48:03] morri — https://clips.twitch.tv/AbcXyz\n"
    )


# --- o registro -------------------------------------------------------------


def test_registro_sobrevive_a_um_arquivo_estragado(tmp_path):
    caminho = tmp_path / "clips.json"
    caminho.write_text("nao e json", encoding="utf-8")
    assert RegistroDeClipes(caminho).itens == []


def test_registro_ignora_campo_desconhecido_de_versao_futura(tmp_path):
    caminho = tmp_path / "clips.json"
    caminho.write_text(json.dumps([
        {"id": "A", "url": "u", "campo_do_futuro": 1}
    ]), encoding="utf-8")
    itens = RegistroDeClipes(caminho).itens
    assert len(itens) == 1 and itens[0].id == "A"


def test_pauta_deixa_de_fora_o_que_foi_descartado(tmp_path):
    registro = RegistroDeClipes(tmp_path / "clips.json")
    registro.adicionar(Clipe(id="A", url="https://c/A", texto="bom"))
    registro.adicionar(Clipe(id="B", url="https://c/B", texto="ruim"))
    registro.decidir("B", False)

    pauta = registro.para_pauta()
    assert "bom" in pauta and "ruim" not in pauta
