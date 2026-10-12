"""
Script para (re)criar as tabelas e popular os dados padrão (tabelas de
apoio: status de presença, cargos, tipos de vínculo, etc.).

Uso:
    python -m src.model.init_db

Em produção, prefira gerenciar as tabelas via Alembic
(`alembic upgrade head`) e rode este script só para semear os dados
padrão em um banco novo/vazio.
"""

from src.model import crud, models
from src.model.database import Base, SessionLocal, engine

# valor default -> lista de textos a garantir na tabela
DADOS_PADRAO = {
    models.StatusPresenca: ("status", ["ATESTADO", "COMPARECEU", "DECLARAÇÃO", "FALTOU"]),
    models.CargoFuncao: (
        "cargo_funcao",
        [
            "ASD", "AUX. DE DISCIPLINA", "AUX. DE ENSINO / TI", "AUX. DE MERENDEIRA",
            "AUX. DE SECRETARIA", "DIRETOR", "MERENDEIRA", "MONITOR / AUX. DE DISCIPLINA",
            "MONITORA / AUX. DE DISCIPLINA", "PORTEIRA", "PORTEIRO", "PROF. / AUX. BIBLIOT.",
            "PROF./APOIO ADM.", "PROF./AUX. BIBLIOT.", "PEDAGOGA./COORD.", "COORDENADORA",
            "PROF./SECRETÁRIA GERAL", "VIGIA",
        ],
    ),
    models.CargaHoraria: ("carga_horaria", ["40H", "25H", "30H"]),
    models.TipoProfessor: (
        "tipo", ["CRECHE", "PRÉ ESCOLA", "FUNDAMENTAL I", "FUNDAMENTAL II", "EJA", "RENASCER"]
    ),
    models.TipoServidor: ("tipo_servidor", ["ADM", "PROF"]),
    models.FormacaoAcademica: (
        "formacao_academica",
        [
            "FUND INCOMPLETO", "CURS. FUNDAMENTAL", "FUND COMPLETO", "ENSINO MÉDIO",
            "CURS. PEDAGOGIA", "ENS. MÉDIO INCOMPLETO", "PEDAGOGIA", "PEDAGOGIA / CIÊNC. BIO",
            "PEDAGOGIA / PSICOPEDAGOGIA", "PEDAGOGIA / ESP ED INFANTIL",
        ],
    ),
    models.TipoVinculo: ("tipo_vinculo", ["SP", "EST"]),
}


def create_tables() -> None:
    """Cria as tabelas a partir dos models (uso rápido em dev; em produção
    prefira `alembic upgrade head`, que fica versionado)."""
    Base.metadata.create_all(bind=engine)


def seed_lookups() -> None:
    """Garante que os valores padrão existam nas tabelas de apoio, sem
    duplicar o que já estiver cadastrado."""
    session = SessionLocal()
    try:
        for model, (attr, valores) in DADOS_PADRAO.items():
            existentes = {getattr(row, attr) for row in session.query(model).all()}
            for valor in valores:
                if valor not in existentes:
                    session.add(model(**{attr: valor}))
        session.commit()
    finally:
        session.close()


def init_db() -> None:
    create_tables()
    seed_lookups()
    # níveis de acesso (admin/operador) + usuário admin padrão, se não houver usuários
    crud.garantir_dados_padrao()


if __name__ == "__main__":
    init_db()
    print("Banco inicializado: tabelas de apoio, níveis de acesso e usuário admin padrão (admin/admin).")
