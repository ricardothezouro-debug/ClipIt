"""O registro local dos clipes -- a pauta de cortes que se monta sozinha."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from clipit.core.paths import clips_path

#: Acima disto o arquivo comeca a pesar sem servir para nada: sao lives antigas.
MAXIMO_GUARDADO = 500


@dataclass
class Clipe:
    id: str
    url: str
    edit_url: str = ""
    texto: str = ""
    quando: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    #: Vira True quando a Twitch confirma que terminou de processar.
    confirmado: bool = False
    #: Escolha do usuario na triagem: None = ainda nao decidiu.
    usar: Optional[bool] = None

    @property
    def horario(self) -> str:
        try:
            return datetime.fromisoformat(self.quando).strftime("%H:%M:%S")
        except ValueError:
            return "--:--:--"


class RegistroDeClipes:
    def __init__(self, caminho: Optional[Path] = None) -> None:
        self.path = Path(caminho or clips_path())
        self.itens: list[Clipe] = self._carregar()

    def _carregar(self) -> list[Clipe]:
        try:
            bruto = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        itens: list[Clipe] = []
        for registro in bruto if isinstance(bruto, list) else []:
            if not isinstance(registro, dict) or "id" not in registro:
                continue
            conhecidos = {c: registro.get(c) for c in Clipe.__annotations__
                          if c in registro}
            try:
                itens.append(Clipe(**conhecidos))
            except TypeError:
                continue
        return itens

    def salvar(self) -> None:
        del self.itens[:-MAXIMO_GUARDADO]
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps([asdict(c) for c in self.itens], indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass

    def adicionar(self, clipe: Clipe) -> Clipe:
        self.itens.append(clipe)
        self.salvar()
        return clipe

    def marcar_confirmado(self, clip_id: str) -> None:
        for clipe in self.itens:
            if clipe.id == clip_id:
                clipe.confirmado = True
                self.salvar()
                return

    def decidir(self, clip_id: str, usar: Optional[bool]) -> None:
        for clipe in self.itens:
            if clipe.id == clip_id:
                clipe.usar = usar
                self.salvar()
                return

    def da_sessao(self, desde: datetime) -> list[Clipe]:
        """Os clipes desta live, do mais novo para o mais velho."""
        recentes = []
        for clipe in self.itens:
            try:
                if datetime.fromisoformat(clipe.quando) >= desde:
                    recentes.append(clipe)
            except ValueError:
                continue
        return list(reversed(recentes))

    def para_pauta(self, clipes: Optional[list[Clipe]] = None) -> str:
        """A lista pronta para colar onde a edicao acontece."""
        escolhidos = clipes if clipes is not None else self.itens
        uteis = [c for c in escolhidos if c.usar is not False]
        if not uteis:
            return "Nenhum clipe nesta lista.\n"
        linhas = ["# Pauta de cortes", ""]
        for clipe in uteis:
            marca = "✔" if clipe.usar else "•"
            linhas.append(f"{marca} {clipe.horario}  {clipe.texto or 'clipe'}")
            linhas.append(f"    {clipe.url}")
            if clipe.edit_url:
                linhas.append(f"    editar: {clipe.edit_url}")
            linhas.append("")
        return "\n".join(linhas)
