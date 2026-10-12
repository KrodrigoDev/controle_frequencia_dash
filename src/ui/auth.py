"""Login e permissões.

A sessão fica num cookie assinado do Flask (o navegador não consegue
alterá-lo). Cada tela e cada ação de gravação conferem o nível de acesso no
servidor — esconder o menu não é a única proteção.
"""

from __future__ import annotations

import secrets
from pathlib import Path

import flask
from dash.exceptions import PreventUpdate

import config
from src.model import crud
from src.model.database import DATA_DIR
from src.model.seguranca import verificar_senha

TODOS = (config.NIVEL_ADMIN, config.NIVEL_OPERADOR)
SOMENTE_ADMIN = (config.NIVEL_ADMIN,)


def chave_secreta() -> str:
    """CF_SECRET_KEY do ambiente ou uma chave gerada uma vez em data/.chave_secreta."""
    import os

    if os.environ.get("CF_SECRET_KEY"):
        return os.environ["CF_SECRET_KEY"]
    arquivo = Path(DATA_DIR) / ".chave_secreta"
    if not arquivo.exists():
        arquivo.write_text(secrets.token_hex(32), encoding="utf-8")
    return arquivo.read_text(encoding="utf-8").strip()


def autenticar(username: str, senha: str) -> tuple[str, dict | None]:
    """('ok' | 'invalido' | 'inativo', usuario). Usuário inexistente e senha
    errada dão a mesma resposta, para não revelar quais usuários existem."""
    usuario = crud.get_usuario_login(username) if username else None
    if usuario is None or not verificar_senha(senha or "", usuario["senha_hash"]):
        return "invalido", None
    if not usuario["ativo"]:
        return "inativo", None
    return "ok", usuario


def iniciar_sessao(usuario: dict, senha_digitada: str) -> None:
    flask.session.clear()
    flask.session["uid"] = int(usuario["id"])
    flask.session["username"] = usuario["username"]
    flask.session["nome"] = usuario["nome"]
    flask.session["nivel"] = usuario["nivel"]
    flask.session["senha_padrao"] = senha_digitada == config.ADMIN_SENHA_PADRAO


def encerrar_sessao() -> None:
    flask.session.clear()


def usuario_atual(revalidar: bool = False) -> dict | None:
    """Usuário logado ({uid, username, nome, nivel, senha_padrao}) ou None.
    `revalidar=True` confere no banco se ele continua ativo e com o mesmo nível
    (usado a cada troca de tela)."""
    if not flask.has_request_context() or "uid" not in flask.session:
        return None
    if revalidar:
        u = crud.get_usuario(flask.session["uid"])
        if u is None or not u["ativo"]:
            encerrar_sessao()
            return None
        flask.session["nivel"] = u["nivel"]
        flask.session["nome"] = u["nome"]
    return dict(flask.session)


def pode(niveis) -> bool:
    u = usuario_atual()
    return bool(u and u.get("nivel") in niveis)


def exigir(niveis=TODOS) -> dict:
    """Para usar no começo de callbacks que gravam ou exportam dados."""
    u = usuario_atual()
    if not u or u.get("nivel") not in niveis:
        raise PreventUpdate
    return u
