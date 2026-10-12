"""
Funções de Create, Read, Update, Delete para servidores, presenças e
tabelas de apoio.

Convenção usada aqui: cada função abre e fecha sua própria sessão do
SQLAlchemy (`with database.get_session() as session:`) e devolve dados já
"desconectados" do ORM — dicts, listas de dicts ou DataFrames — nunca
objetos ORM vivos. Isso evita erros de `DetachedInstanceError` nas telas,
que usam os dados depois da sessão ter sido fechada.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
from sqlalchemy import func, select

import config
from src.model import models
from src.model.database import get_session
from src.model.seguranca import hash_senha

# ---------------------------------------------------------------------------
# Registro das tabelas de apoio (lookups): chave amigável -> (Model, atributo)
# ---------------------------------------------------------------------------

LOOKUPS = {
    "status_presenca": (models.StatusPresenca, "status"),
    "cargo_funcao": (models.CargoFuncao, "cargo_funcao"),
    "carga_horaria": (models.CargaHoraria, "carga_horaria"),
    "tipo_professor": (models.TipoProfessor, "tipo"),
    "tipo_servidor": (models.TipoServidor, "tipo_servidor"),
    "formacao_academica": (models.FormacaoAcademica, "formacao_academica"),
    "tipo_vinculo": (models.TipoVinculo, "tipo_vinculo"),
}

# colunas de fato_servidor / fato_presenca que referenciam cada lookup,
# usado para bloquear exclusão de itens em uso
_FK_REFERENCES = {
    "status_presenca": (models.Presenca, "id_status_presenca"),
    "cargo_funcao": (models.Servidor, "id_cargo_funcao"),
    "carga_horaria": (models.Servidor, "id_carga_horaria"),
    "tipo_professor": (models.Servidor, "id_tipo_professor"),
    "tipo_servidor": (models.Servidor, "id_tipo_servidor"),
    "formacao_academica": (models.Servidor, "id_formacao_academica"),
    "tipo_vinculo": (models.Servidor, "id_tipo_vinculo"),
}


def lookup_options(chave: str) -> dict[int, str]:
    """{id: rótulo} de uma tabela de apoio, pronto para popular selects."""
    model, attr = LOOKUPS[chave]
    with get_session() as session:
        linhas = session.execute(select(model)).scalars().all()
        return {row.id: getattr(row, attr) for row in linhas}


def add_lookup(chave: str, valor: str) -> int:
    model, attr = LOOKUPS[chave]
    with get_session() as session:
        item = model(**{attr: valor})
        session.add(item)
        session.commit()
        return item.id


def update_lookup(chave: str, item_id: int, valor: str) -> None:
    model, attr = LOOKUPS[chave]
    with get_session() as session:
        item = session.get(model, item_id)
        if item is not None:
            setattr(item, attr, valor)
            session.commit()


def lookup_in_use(chave: str, item_id: int) -> bool:
    ref_model, fk_col = _FK_REFERENCES[chave]
    with get_session() as session:
        qtd = session.execute(
            select(func.count()).select_from(ref_model).where(
                getattr(ref_model, fk_col) == item_id
            )
        ).scalar_one()
        return qtd > 0


def delete_lookup(chave: str, item_id: int) -> None:
    model, _ = LOOKUPS[chave]
    with get_session() as session:
        item = session.get(model, item_id)
        if item is not None:
            session.delete(item)
            session.commit()


# ---------------------------------------------------------------------------
# Servidores (fato_servidor)
# ---------------------------------------------------------------------------

COLUNAS_SERVIDOR = [
    "id", "matricula", "nome_servidor", "cpf", "tipo_vinculo", "cargo_funcao", "carga_horaria",
    "tipo_servidor", "tipo_professor", "formacao_academica", "ativo",
]


def list_servidores(apenas_ativos: bool = False) -> pd.DataFrame:
    """DataFrame de servidores já com os rótulos das tabelas de apoio
    (em vez dos ids), pronto para exibir em tela."""
    with get_session() as session:
        query = select(models.Servidor)
        if apenas_ativos:
            query = query.where(models.Servidor.ativo.is_(True))
        servidores = session.execute(query).scalars().all()

        linhas = []
        for s in servidores:
            linhas.append(
                {
                    "id": s.id,
                    "matricula": s.matricula,
                    "nome_servidor": s.nome_servidor,
                    "cpf": s.cpf,
                    "tipo_vinculo": s.tipo_vinculo.tipo_vinculo if s.tipo_vinculo else None,
                    "cargo_funcao": s.cargo_funcao.cargo_funcao if s.cargo_funcao else None,
                    "carga_horaria": s.carga_horaria.carga_horaria if s.carga_horaria else None,
                    "tipo_servidor": s.tipo_servidor.tipo_servidor if s.tipo_servidor else None,
                    "tipo_professor": s.tipo_professor.tipo if s.tipo_professor else None,
                    "formacao_academica": (
                        s.formacao_academica.formacao_academica if s.formacao_academica else None
                    ),
                    "ativo": s.ativo,
                }
            )
        return pd.DataFrame(linhas, columns=COLUNAS_SERVIDOR)


def get_servidor(servidor_id: int) -> dict | None:
    """Dados "crus" (com os ids das FKs) de um servidor, para pré-preencher
    o formulário de edição."""
    with get_session() as session:
        s = session.get(models.Servidor, servidor_id)
        if s is None:
            return None
        return {
            "id": s.id,
            "matricula": s.matricula,
            "nome_servidor": s.nome_servidor,
            "cpf": s.cpf,
            "id_tipo_vinculo": s.id_tipo_vinculo,
            "id_cargo_funcao": s.id_cargo_funcao,
            "id_carga_horaria": s.id_carga_horaria,
            "id_tipo_servidor": s.id_tipo_servidor,
            "id_tipo_professor": s.id_tipo_professor,
            "id_formacao_academica": s.id_formacao_academica,
            "ativo": s.ativo,
        }


def add_servidor(dados: dict) -> int:
    with get_session() as session:
        servidor = models.Servidor(**dados)
        session.add(servidor)
        session.commit()
        return servidor.id


def update_servidor(servidor_id: int, dados: dict) -> None:
    with get_session() as session:
        servidor = session.get(models.Servidor, servidor_id)
        if servidor is None:
            return
        for campo, valor in dados.items():
            setattr(servidor, campo, valor)
        session.commit()


def delete_servidor(servidor_id: int, hard: bool = False) -> None:
    """Por padrão faz exclusão lógica (ativo=False), preservando o
    histórico de presenças. `hard=True` remove a linha de fato (só permitido
    se não houver presenças associadas — ver `servidor_tem_presencas`)."""
    with get_session() as session:
        servidor = session.get(models.Servidor, servidor_id)
        if servidor is None:
            return
        if hard:
            session.delete(servidor)
        else:
            servidor.ativo = False
        session.commit()


def servidor_tem_presencas(servidor_id: int) -> bool:
    with get_session() as session:
        qtd = session.execute(
            select(func.count())
            .select_from(models.Presenca)
            .where(models.Presenca.id_servidor == servidor_id)
        ).scalar_one()
        return qtd > 0


# ---------------------------------------------------------------------------
# Calendário — criado sob demanda
# ---------------------------------------------------------------------------

def _get_or_create_calendario_id(session, data: dt.date) -> int:
    cal = session.execute(
        select(models.Calendario).where(models.Calendario.data == data)
    ).scalar_one_or_none()
    if cal is not None:
        return cal.id
    cal = models.Calendario(
        ano=data.year, mes=data.month, dia=data.day, data=data, fim_de_semana=data.weekday() >= 5
    )
    session.add(cal)
    session.flush()  # garante que cal.id já esteja disponível sem precisar commitar
    return cal.id


# ---------------------------------------------------------------------------
# Presenças (fato_presenca)
# ---------------------------------------------------------------------------

def upsert_presenca(servidor_id: int, data: dt.date, status_id: int, observacao: str = "") -> None:
    with get_session() as session:
        calendario_id = _get_or_create_calendario_id(session, data)
        presenca = session.execute(
            select(models.Presenca).where(
                models.Presenca.id_servidor == servidor_id,
                models.Presenca.id_calendario == calendario_id,
            )
        ).scalar_one_or_none()
        if presenca is not None:
            presenca.id_status_presenca = status_id
            presenca.observacao = observacao
        else:
            session.add(
                models.Presenca(
                    id_servidor=servidor_id,
                    id_calendario=calendario_id,
                    id_status_presenca=status_id,
                    observacao=observacao,
                )
            )
        session.commit()


def bulk_upsert_presenca(data: dt.date, lancamentos: list[dict]) -> None:
    """Lança presença em lote para um dia (chamada). `lancamentos`:
    [{"id_servidor":.., "id_status_presenca":.., "observacao": ..}, ...].
    Tudo em uma única transação."""
    with get_session() as session:
        calendario_id = _get_or_create_calendario_id(session, data)
        for item in lancamentos:
            presenca = session.execute(
                select(models.Presenca).where(
                    models.Presenca.id_servidor == item["id_servidor"],
                    models.Presenca.id_calendario == calendario_id,
                )
            ).scalar_one_or_none()
            if presenca is not None:
                presenca.id_status_presenca = item["id_status_presenca"]
                presenca.observacao = item.get("observacao", "")
            else:
                session.add(
                    models.Presenca(
                        id_servidor=item["id_servidor"],
                        id_calendario=calendario_id,
                        id_status_presenca=item["id_status_presenca"],
                        observacao=item.get("observacao", ""),
                    )
                )
        session.commit()


def delete_presenca(presenca_id: int) -> None:
    with get_session() as session:
        presenca = session.get(models.Presenca, presenca_id)
        if presenca is not None:
            session.delete(presenca)
            session.commit()


def presencas_do_dia(data: dt.date) -> dict[int, dict]:
    """{id_servidor: {"id_status_presenca":.., "observacao":..}} já
    lançados para uma data, para pré-preencher a tela de chamada."""
    with get_session() as session:
        cal = session.execute(
            select(models.Calendario).where(models.Calendario.data == data)
        ).scalar_one_or_none()
        if cal is None:
            return {}
        presencas = session.execute(
            select(models.Presenca).where(models.Presenca.id_calendario == cal.id)
        ).scalars().all()
        return {
            p.id_servidor: {
                "id_status_presenca": p.id_status_presenca,
                "observacao": p.observacao or "",
            }
            for p in presencas
        }


# ---------------------------------------------------------------------------
# Visão consolidada para o dashboard
# ---------------------------------------------------------------------------

def presenca_detalhada(inicio: dt.date | None = None, fim: dt.date | None = None) -> pd.DataFrame:
    """Uma linha por presença lançada, já com os dados do servidor e os
    rótulos das tabelas de apoio — pronta para filtrar/agregar.
    `inicio`/`fim` (opcionais, inclusivos) limitam o período no próprio banco."""
    S, P, C = models.Servidor, models.Presenca, models.Calendario
    query = (
        select(
            P.id.label("id_presenca"),
            S.id.label("id_servidor"),
            S.nome_servidor,
            S.matricula,
            S.ativo,
            models.CargoFuncao.cargo_funcao,
            models.TipoServidor.tipo_servidor,
            models.TipoProfessor.tipo.label("tipo_professor"),
            models.TipoVinculo.tipo_vinculo,
            models.CargaHoraria.carga_horaria,
            C.data,
            C.ano,
            C.mes,
            C.dia,
            C.fim_de_semana,
            models.StatusPresenca.status,
            P.observacao,
        )
        .join(S, P.id_servidor == S.id)
        .join(C, P.id_calendario == C.id)
        .join(models.StatusPresenca, P.id_status_presenca == models.StatusPresenca.id)
        .outerjoin(models.CargoFuncao, S.id_cargo_funcao == models.CargoFuncao.id)
        .outerjoin(models.TipoServidor, S.id_tipo_servidor == models.TipoServidor.id)
        .outerjoin(models.TipoProfessor, S.id_tipo_professor == models.TipoProfessor.id)
        .outerjoin(models.TipoVinculo, S.id_tipo_vinculo == models.TipoVinculo.id)
        .outerjoin(models.CargaHoraria, S.id_carga_horaria == models.CargaHoraria.id)
    )
    if inicio is not None:
        query = query.where(C.data >= inicio)
    if fim is not None:
        query = query.where(C.data <= fim)
    with get_session() as session:
        linhas = session.execute(query).mappings().all()
    colunas = [c.name for c in query.selected_columns]
    return pd.DataFrame([dict(r) for r in linhas], columns=colunas)


def periodo_com_dados() -> tuple[dt.date | None, dt.date | None]:
    """Primeira e última data com presença lançada (None, None se vazio)."""
    with get_session() as session:
        menor, maior = session.execute(
            select(func.min(models.Calendario.data), func.max(models.Calendario.data))
            .join(models.Presenca, models.Presenca.id_calendario == models.Calendario.id)
        ).one()
        return menor, maior


# ---------------------------------------------------------------------------
# Usuários e níveis de acesso (autenticação)
# ---------------------------------------------------------------------------

def _validar_senha(senha: str) -> None:
    if not senha or len(senha) < config.SENHA_MINIMA:
        raise ValueError(f"A senha deve ter pelo menos {config.SENHA_MINIMA} caracteres.")


def _normalizar_username(username: str) -> str:
    return (username or "").strip().lower()


def garantir_dados_padrao() -> None:
    """Idempotente: garante os níveis de acesso e, se o banco não tiver
    NENHUM usuário, cria o admin padrão (usuário/senha definidos em config.py).
    Chamada pelo init_db e também pela tela de login."""
    with get_session() as session:
        for nivel in config.NIVEIS_ACESSO:
            existe = session.execute(
                select(models.NivelAcesso).where(models.NivelAcesso.nivel == nivel)
            ).scalar_one_or_none()
            if existe is None:
                session.add(models.NivelAcesso(nivel=nivel))
        session.flush()

        total = session.execute(select(func.count()).select_from(models.Usuario)).scalar_one()
        if total == 0:
            nivel_admin = session.execute(
                select(models.NivelAcesso).where(models.NivelAcesso.nivel == config.NIVEL_ADMIN)
            ).scalar_one()
            session.add(
                models.Usuario(
                    username=config.ADMIN_USERNAME_PADRAO,
                    nome="Administrador",
                    senha_hash=hash_senha(config.ADMIN_SENHA_PADRAO),
                    id_nivel_acesso=nivel_admin.id,
                    ativo=True,
                )
            )
        session.commit()


def list_niveis() -> dict[int, str]:
    """{id: nível} — 'admin', 'operador'."""
    with get_session() as session:
        linhas = session.execute(select(models.NivelAcesso)).scalars().all()
        return {n.id: n.nivel for n in linhas}


def get_usuario_login(username: str) -> dict | None:
    """Dados do usuário para autenticação (inclui o hash da senha). Nunca
    exibir este dict em tela."""
    with get_session() as session:
        u = session.execute(
            select(models.Usuario).where(models.Usuario.username == _normalizar_username(username))
        ).scalar_one_or_none()
        if u is None:
            return None
        return {
            "id": u.id,
            "username": u.username,
            "nome": u.nome,
            "senha_hash": u.senha_hash,
            "nivel": u.nivel_acesso.nivel,
            "ativo": u.ativo,
        }


def list_usuarios() -> pd.DataFrame:
    with get_session() as session:
        usuarios = session.execute(
            select(models.Usuario).order_by(models.Usuario.username)
        ).scalars().all()
        return pd.DataFrame(
            columns=["id", "username", "nome", "nivel_acesso", "ativo"],
            data=[
                {
                    "id": u.id,
                    "username": u.username,
                    "nome": u.nome,
                    "nivel_acesso": u.nivel_acesso.nivel,
                    "ativo": u.ativo,
                }
                for u in usuarios
            ],
        )


def get_usuario(usuario_id: int) -> dict | None:
    with get_session() as session:
        u = session.get(models.Usuario, usuario_id)
        if u is None:
            return None
        return {
            "id": u.id,
            "username": u.username,
            "nome": u.nome,
            "id_nivel_acesso": u.id_nivel_acesso,
            "nivel": u.nivel_acesso.nivel,
            "ativo": u.ativo,
        }


def add_usuario(username: str, nome: str, senha: str, id_nivel_acesso: int) -> int:
    username = _normalizar_username(username)
    if not username or not (nome or "").strip():
        raise ValueError("Informe o usuário e o nome.")
    _validar_senha(senha)
    with get_session() as session:
        if session.execute(
            select(models.Usuario).where(models.Usuario.username == username)
        ).scalar_one_or_none():
            raise ValueError(f"O usuário '{username}' já existe.")
        usuario = models.Usuario(
            username=username,
            nome=nome.strip(),
            senha_hash=hash_senha(senha),
            id_nivel_acesso=id_nivel_acesso,
            ativo=True,
        )
        session.add(usuario)
        session.commit()
        return usuario.id


def update_usuario(usuario_id: int, nome: str, id_nivel_acesso: int, ativo: bool) -> None:
    """Atualiza nome, nível e situação. Impede que o sistema fique sem
    nenhum administrador ativo."""
    with get_session() as session:
        u = session.get(models.Usuario, usuario_id)
        if u is None:
            return
        nivel_novo = session.get(models.NivelAcesso, id_nivel_acesso).nivel
        era_admin_ativo = u.nivel_acesso.nivel == config.NIVEL_ADMIN and u.ativo
        continua_admin_ativo = nivel_novo == config.NIVEL_ADMIN and ativo
        if era_admin_ativo and not continua_admin_ativo:
            outros = session.execute(
                select(func.count())
                .select_from(models.Usuario)
                .join(models.NivelAcesso)
                .where(
                    models.NivelAcesso.nivel == config.NIVEL_ADMIN,
                    models.Usuario.ativo.is_(True),
                    models.Usuario.id != usuario_id,
                )
            ).scalar_one()
            if outros == 0:
                raise ValueError("Deve existir ao menos um administrador ativo no sistema.")
        u.nome = nome.strip()
        u.id_nivel_acesso = id_nivel_acesso
        u.ativo = ativo
        session.commit()


def alterar_senha(usuario_id: int, nova_senha: str) -> None:
    _validar_senha(nova_senha)
    with get_session() as session:
        u = session.get(models.Usuario, usuario_id)
        if u is not None:
            u.senha_hash = hash_senha(nova_senha)
            session.commit()
