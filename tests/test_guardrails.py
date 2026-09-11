"""O que o build congelado faria -- verificado aqui, onde ainda da tempo.

O portable do Sidekick so carrega o que esta nos `hiddenimports` do .spec. Um
`import requests` esquecido instala o plugin e ele simplesmente nunca abre, sem
erro nenhum na tela. Estes testes simulam essa restricao.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent / "src" / "clipit"

PERMITIDOS = set(sys.stdlib_module_names) | {"PySide6", "clipit", "streamer_sidekick"}


def _modulos(pasta: Path):
    for arquivo in sorted(pasta.rglob("*.py")):
        yield arquivo, ast.parse(arquivo.read_text(encoding="utf-8"))


def _raizes(no: ast.AST) -> set[str]:
    if isinstance(no, ast.Import):
        return {alias.name.split(".")[0] for alias in no.names}
    if isinstance(no, ast.ImportFrom) and no.level == 0 and no.module:
        return {no.module.split(".")[0]}
    return set()


def _raizes_importadas(arvore: ast.AST) -> set[str]:
    raizes: set[str] = set()
    for no in ast.walk(arvore):
        raizes |= _raizes(no)
    return raizes


def _imports_de_topo(arvore: ast.Module) -> set[str]:
    """So o que o interpretador carrega ao importar o modulo.

    Um import dentro de funcao e adiado; dentro de `try` e opcional. O que
    derruba o plugin congelado e o import de topo, porque acontece sempre.
    """
    raizes: set[str] = set()
    for no in arvore.body:
        raizes |= _raizes(no)
    return raizes


def _imports_desprotegidos(arvore: ast.Module) -> set[str]:
    """Imports aninhados que NAO estao dentro de um try/except."""
    protegidos: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Try):
            for interno in ast.walk(no):
                protegidos |= _raizes(interno)
    return _raizes_importadas(arvore) - protegidos


def test_nada_de_dependencia_de_terceiros_no_topo():
    """O que importa e o topo: e o unico import que acontece sempre."""
    for arquivo, arvore in _modulos(RAIZ):
        estranhos = _imports_de_topo(arvore) - PERMITIDOS
        assert not estranhos, f"{arquivo.name} importa {estranhos} no topo"


def test_dependencia_opcional_sempre_dentro_de_try():
    """Pode depender de algo de fora -- desde que a falta nao derrube nada.

    O certifi e o caso legitimo: quando existe, conserta os certificados do
    macOS; quando nao existe, o codigo segue com a loja do sistema.
    """
    for arquivo, arvore in _modulos(RAIZ):
        estranhos = _imports_desprotegidos(arvore) - PERMITIDOS
        assert not estranhos, (
            f"{arquivo.name} importa {estranhos} sem try/except -- "
            f"no portable isso vira ModuleNotFoundError"
        )


def test_o_core_nao_conhece_qt():
    """core/ existe para ser testavel sem display. Qt la dentro mata isso."""
    for arquivo, arvore in _modulos(RAIZ / "core"):
        assert "PySide6" not in _raizes_importadas(arvore), \
            f"{arquivo.name} importou PySide6"


def test_nada_de_caminho_de_windows_escrito_na_mao():
    """Mensagem com C:\\ ou %APPDATA% e um plugin que so pensou num sistema."""
    proibidos = ("C:\\", "%APPDATA%", "\\Program Files")
    for arquivo, arvore in _modulos(RAIZ):
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Constant) or not isinstance(no.value, str):
                continue
            for proibido in proibidos:
                assert proibido not in no.value, f"{arquivo.name}: {no.value!r}"


def test_creationflags_e_startfile_so_dentro_de_guarda_de_plataforma():
    """`creationflags` nao existe no macOS e `os.startfile` so existe no Windows.

    Nao proibimos: exigimos que estejam atras de um `sys.platform == "win32"`.
    """
    for arquivo, _ in _modulos(RAIZ):
        texto = arquivo.read_text(encoding="utf-8")
        for marca in ("creationflags", "os.startfile"):
            if marca in texto:
                assert 'sys.platform == "win32"' in texto, \
                    f"{arquivo.name} usa {marca} sem guarda de plataforma"


def test_o_token_nunca_entra_no_repositorio():
    """Nao basta o .gitignore existir: ele tem que cobrir o que a gente grava."""
    ignorados = (Path(__file__).resolve().parent.parent / ".gitignore").read_text()
    assert "tokens.json" in ignorados
    assert ".env" in ignorados
