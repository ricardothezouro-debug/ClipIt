"""Sobe a pagina inteira sem display e derruba tudo em seguida.

Os testes de unidade nao pegam a classe de bug que mais doi num plugin: falhas
que so acontecem com a aplicacao Qt de pe. Roda no CI, nos dois sistemas.

    QT_QPA_PLATFORM=offscreen PYTHONPATH=src python scripts/smoke_test.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from clipit import __version__  # noqa: E402
from clipit import module  # noqa: E402
from clipit.core.paths import data_dir  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)

    print(f"versao     : {__version__}")
    print(f"plataforma : {sys.platform}")
    print(f"dados      : {data_dir()}")

    info = module.module_info()
    print(f"module_info: {info.title} ({info.module_id})")
    print(f"help_text  : {len(module.help_text())} caracteres")

    pagina = module.build_page()
    print(f"build_page : {type(pagina).__name__}")

    for indice in range(pagina.abas.count()):
        pagina.abas.setCurrentIndex(indice)
        app.processEvents()
        print(f"  aba ok   : {pagina.abas.tabText(indice)}")

    conectado = pagina.servico.conectado()
    print(f"conta      : {'conectada' if conectado else 'nao conectada'}")

    pagina.encerrar()
    app.processEvents()
    print("smoke test OK")

    # os._exit evita que o teardown do Qt segure o processo no CI -- mas ele
    # NAO descarrega os buffers. Com a saida indo para um pipe (todo CI), o
    # stdout fica com buffer de bloco e tudo o que foi impresso ate aqui seria
    # descartado: o teste passaria mudo, sem nenhuma linha.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


if __name__ == "__main__":
    sys.exit(main())
