"""
Configuração do SQLAlchemy e da engine do banco de dados.

Por padrão usamos SQLite (um único arquivo em `data/controle_frequencia.db`),
o que já é suficiente para uma escola. Se no futuro for preciso um banco
"de verdade" (ex.: Postgres em um servidor, para múltiplos usuários
gravando ao mesmo tempo), basta definir a variável de ambiente
DATABASE_URL — nenhum outro arquivo do projeto precisa mudar, pois todo o
resto (models, crud, páginas) fala apenas com a engine/Session do SQLAlchemy.

Exemplos de DATABASE_URL:
    sqlite:///./data/controle_frequencia.db          (padrão)
    postgresql+psycopg2://usuario:senha@host:5432/nome_do_banco
"""

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Raiz do projeto (duas pastas acima deste arquivo: src/model/database.py -> raiz)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_DATABASE_URL = f"sqlite:///{(DATA_DIR / 'controle_frequencia.db').as_posix()}"
DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

Base = declarative_base()


def get_session():
    """Retorna uma nova sessão do SQLAlchemy. Use com `with get_session() as s:`."""
    return SessionLocal()
