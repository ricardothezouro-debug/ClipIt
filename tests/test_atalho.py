"""O atalho, com um backend falso -- o CI nao tem o Sidekick instalado."""
from __future__ import annotations

from clipit.core import atalho


class _BackendFalso:
    def __init__(self, disponivel: bool = True) -> None:
        self._disponivel = disponivel
        self.registrados: dict[int, tuple[str, object]] = {}
        self._proximo = 1

    def is_available(self) -> bool:
        return self._disponivel

    def normalize(self, s: str) -> str:
        return s.strip().replace(" ", "")

    def validate(self, s: str) -> None:
        if "+" not in s:
            raise ValueError("Use pelo menos um modificador")

    def register(self, s: str, cb) -> int:
        handle = self._proximo
        self._proximo += 1
        self.registrados[handle] = (s, cb)
        return handle

    def unregister(self, handle) -> None:
        self.registrados.pop(handle, None)


def test_registra_e_remove(monkeypatch):
    falso = _BackendFalso()
    monkeypatch.setattr(atalho, "_backend", falso)
    a = atalho.Atalho()

    assert a.registrar("Ctrl+Alt+K", lambda: None) == ""
    assert a.ativo and a.sequencia == "Ctrl+Alt+K"
    assert len(falso.registrados) == 1

    a.remover()
    assert not a.ativo and falso.registrados == {}


def test_registrar_de_novo_troca_o_anterior(monkeypatch):
    """Dois atalhos vivos ao mesmo tempo clipariam duas vezes."""
    falso = _BackendFalso()
    monkeypatch.setattr(atalho, "_backend", falso)
    a = atalho.Atalho()
    a.registrar("Ctrl+Alt+K", lambda: None)
    a.registrar("Ctrl+Alt+L", lambda: None)
    assert [s for s, _ in falso.registrados.values()] == ["Ctrl+Alt+L"]


def test_sequencia_invalida_devolve_o_motivo_sem_registrar(monkeypatch):
    falso = _BackendFalso()
    monkeypatch.setattr(atalho, "_backend", falso)
    a = atalho.Atalho()
    motivo = a.registrar("K", lambda: None)
    assert "modificador" in motivo
    assert not a.ativo


def test_sem_sidekick_explica_em_vez_de_quebrar(monkeypatch):
    monkeypatch.setattr(atalho, "_backend", None)
    assert atalho.disponivel() is False
    assert "Sidekick" in atalho.validar("Ctrl+Alt+K")
    assert atalho.Atalho().registrar("Ctrl+Alt+K", lambda: None) != ""


def test_vazio_e_sem_atalho_e_nao_e_erro(monkeypatch):
    monkeypatch.setattr(atalho, "_backend", _BackendFalso())
    a = atalho.Atalho()
    assert a.registrar("", lambda: None) == ""
    assert not a.ativo


def test_o_callback_registrado_e_o_que_o_backend_vai_chamar(monkeypatch):
    falso = _BackendFalso()
    monkeypatch.setattr(atalho, "_backend", falso)
    chamadas = []
    atalho.Atalho().registrar("Ctrl+Alt+K", lambda: chamadas.append(1))
    _, cb = next(iter(falso.registrados.values()))
    cb()
    assert chamadas == [1]
