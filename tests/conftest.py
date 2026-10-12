"""Banco de teste temporário com dados fictícios (o banco real não é tocado)."""

import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_tmp = tempfile.mkdtemp(prefix="cf_teste_")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmp, 'teste.db').as_posix()}"
os.environ.setdefault("CF_SECRET_KEY", "chave-de-teste")

import pytest  # noqa: E402

from scripts.dados_ficticios import popular  # noqa: E402

MESES = [(2026, 3), (2026, 4)]
popular(MESES)


@pytest.fixture(scope="session")
def meses():
    return MESES
