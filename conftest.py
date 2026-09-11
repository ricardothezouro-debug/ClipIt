"""Deixa `src/` importavel nos testes sem precisar instalar o pacote."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
