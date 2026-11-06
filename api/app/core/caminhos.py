"""Resolucao do diretorio de dados versionados (`data/`).

Mesma logica de `app.seed`: em container, `data/` e montado em `/data`; fora
dele, fica na raiz do repositorio. Um modulo so para as duas pontas (seed e
sprites estaticos) nao divergirem sobre onde o acervo mora.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

_RAIZ_DO_REPOSITORIO: Final[Path] = Path(__file__).resolve().parent.parent.parent.parent

DIR_DADOS: Final[Path] = Path("/data") if Path("/data").is_dir() else _RAIZ_DO_REPOSITORIO / "data"
DIR_SPRITES: Final[Path] = DIR_DADOS / "sprites"
