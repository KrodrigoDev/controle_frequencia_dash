"""
Models ORM (SQLAlchemy) do domínio de controle de frequência.

Mantém a mesma estrutura lógica da planilha original (fato_servidor,
fato_presenca + tabelas de apoio), agora como tabelas reais de banco,
versionadas pelo Alembic (ver pasta migrations/).
"""

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from src.model.database import Base


# ---------------------------------------------------------------------------
# Tabelas de apoio (lookups)
# ---------------------------------------------------------------------------

class StatusPresenca(Base):
    __tablename__ = "status_presenca"
    id = Column(Integer, primary_key=True)
    status = Column(String(50), nullable=False, unique=True)


class CargoFuncao(Base):
    __tablename__ = "cargo_funcao"
    id = Column(Integer, primary_key=True)
    cargo_funcao = Column(String(100), nullable=False, unique=True)


class CargaHoraria(Base):
    __tablename__ = "carga_horaria"
    id = Column(Integer, primary_key=True)
    carga_horaria = Column(String(20), nullable=False, unique=True)


class TipoProfessor(Base):
    __tablename__ = "tipo_professor"
    id = Column(Integer, primary_key=True)
    tipo = Column(String(50), nullable=False, unique=True)


class TipoServidor(Base):
    __tablename__ = "tipo_servidor"
    id = Column(Integer, primary_key=True)
    tipo_servidor = Column(String(20), nullable=False, unique=True)


class FormacaoAcademica(Base):
    __tablename__ = "formacao_academica"
    id = Column(Integer, primary_key=True)
    formacao_academica = Column(String(100), nullable=False, unique=True)


class TipoVinculo(Base):
    __tablename__ = "tipo_vinculo"
    id = Column(Integer, primary_key=True)
    tipo_vinculo = Column(String(20), nullable=False, unique=True)


# ---------------------------------------------------------------------------
# Dimensão de datas — criada sob demanda quando uma presença é lançada
# ---------------------------------------------------------------------------

class Calendario(Base):
    __tablename__ = "calendario"
    id = Column(Integer, primary_key=True)
    ano = Column(Integer, nullable=False)
    mes = Column(Integer, nullable=False)
    dia = Column(Integer, nullable=False)
    data = Column(Date, nullable=False, unique=True)
    fim_de_semana = Column(Boolean, default=False, nullable=False)


# ---------------------------------------------------------------------------
# Servidor (fato_servidor)
# ---------------------------------------------------------------------------

class Servidor(Base):
    __tablename__ = "fato_servidor"
    id = Column(Integer, primary_key=True)
    matricula = Column(String(30))
    nome_servidor = Column(String(150), nullable=False)
    cpf = Column(String(20))
    ativo = Column(Boolean, default=True, nullable=False)

    id_tipo_vinculo = Column(Integer, ForeignKey("tipo_vinculo.id"))
    id_cargo_funcao = Column(Integer, ForeignKey("cargo_funcao.id"))
    id_carga_horaria = Column(Integer, ForeignKey("carga_horaria.id"))
    id_carga_horaria_complementar = Column(Integer, ForeignKey("carga_horaria.id"))
    id_tipo_servidor = Column(Integer, ForeignKey("tipo_servidor.id"))
    id_tipo_professor = Column(Integer, ForeignKey("tipo_professor.id"))
    id_formacao_academica = Column(Integer, ForeignKey("formacao_academica.id"))

    tipo_vinculo = relationship("TipoVinculo", foreign_keys=[id_tipo_vinculo])
    cargo_funcao = relationship("CargoFuncao", foreign_keys=[id_cargo_funcao])
    carga_horaria = relationship("CargaHoraria", foreign_keys=[id_carga_horaria])
    carga_horaria_complementar = relationship(
        "CargaHoraria", foreign_keys=[id_carga_horaria_complementar]
    )
    tipo_servidor = relationship("TipoServidor", foreign_keys=[id_tipo_servidor])
    tipo_professor = relationship("TipoProfessor", foreign_keys=[id_tipo_professor])
    formacao_academica = relationship(
        "FormacaoAcademica", foreign_keys=[id_formacao_academica]
    )

    presencas = relationship(
        "Presenca", back_populates="servidor", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Presença (fato_presenca)
# ---------------------------------------------------------------------------

class Presenca(Base):
    __tablename__ = "fato_presenca"
    __table_args__ = (
        UniqueConstraint("id_servidor", "id_calendario", name="uq_presenca_servidor_dia"),
    )

    id = Column(Integer, primary_key=True)
    id_servidor = Column(Integer, ForeignKey("fato_servidor.id"), nullable=False)
    id_calendario = Column(Integer, ForeignKey("calendario.id"), nullable=False)
    id_status_presenca = Column(Integer, ForeignKey("status_presenca.id"), nullable=False)
    observacao = Column(Text)

    servidor = relationship("Servidor", back_populates="presencas")
    calendario = relationship("Calendario")
    status_presenca = relationship("StatusPresenca")


# ---------------------------------------------------------------------------
# Autenticação: níveis de acesso e usuários do sistema
# ---------------------------------------------------------------------------

class NivelAcesso(Base):
    """Perfis de permissão: 'admin' (tudo) e 'operador' (lança presença e
    consulta a visão geral). Os valores são semeados por init_db/crud."""

    __tablename__ = "nivel_acesso"
    id = Column(Integer, primary_key=True)
    nivel = Column(String(30), nullable=False, unique=True)


class Usuario(Base):
    __tablename__ = "usuario"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), nullable=False, unique=True)
    nome = Column(String(150), nullable=False)
    senha_hash = Column(String(255), nullable=False)
    id_nivel_acesso = Column(Integer, ForeignKey("nivel_acesso.id"), nullable=False)
    ativo = Column(Boolean, default=True, nullable=False)

    nivel_acesso = relationship("NivelAcesso")
