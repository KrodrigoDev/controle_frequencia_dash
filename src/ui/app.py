"""Fábrica do app Dash: login, menu lateral e troca de telas."""

from __future__ import annotations

import logging
from pathlib import Path

import flask
from dash import Dash, Input, Output, State, callback, dcc, html, no_update

import config
from src.model import crud
from src.ui import auth
from src.ui import componentes as c
from src.ui.pages import chamada, fechamento, grupos, individual, servidores, tabelas, usuarios, visao_geral

log = logging.getLogger(__name__)
RAIZ = Path(__file__).resolve().parents[2]
ASSETS = RAIZ / "assets"

# rota -> (rótulo no menu, seção do menu, quem acessa, função que monta a tela)
PAGINAS = {
    "/": ("Visão geral", "Acompanhar", auth.TODOS, visao_geral.layout),
    "/servidor": ("Por servidor", "Acompanhar", auth.TODOS, individual.layout),
    "/grupos": ("Por grupo", "Acompanhar", auth.TODOS, grupos.layout),
    "/chamada": ("Fazer chamada", "Lançar", auth.TODOS, chamada.layout),
    "/fechamento": ("Fechamento do mês", "Relatórios", auth.TODOS, fechamento.layout),
    "/servidores": ("Servidores", "Cadastros", auth.SOMENTE_ADMIN, servidores.layout),
    "/tabelas": ("Tabelas de apoio", "Cadastros", auth.SOMENTE_ADMIN, tabelas.layout),
    "/usuarios": ("Usuários", "Cadastros", auth.SOMENTE_ADMIN, usuarios.layout),
    "/senha": ("Minha senha", None, auth.TODOS, usuarios.layout_minha_senha),
}


def _logo_src() -> str | None:
    for ext in ("png", "jpg", "jpeg", "svg", "webp"):
        arq = ASSETS / f"logo.{ext}"
        if arq.exists():
            return f"/assets/logo.{ext}"
    return None


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def layout_login() -> html.Div:
    logo = _logo_src()
    return html.Div(html.Div([
        html.Img(src=logo) if logo else None,
        html.H1(config.NOME_SISTEMA),
        html.P("Acesso restrito a usuários autorizados"),
        html.Div([html.Label("Usuário"), dcc.Input(id="login-usuario", type="text", autoFocus=True,
                                                   autoComplete="username")], className="campo"),
        html.Div([html.Label("Senha"), dcc.Input(id="login-senha", type="password", n_submit=0,
                                                 autoComplete="current-password")], className="campo"),
        html.Button("Entrar", id="login-entrar", className="btn primario", n_clicks=0),
        html.Div(id="login-msg"),
        dcc.Location(id="login-redir", refresh=True),
    ], className="login-caixa"), className="login-fundo")


@callback(
    Output("login-msg", "children"), Output("login-redir", "href"),
    Input("login-entrar", "n_clicks"), Input("login-senha", "n_submit"),
    State("login-usuario", "value"), State("login-senha", "value"),
    prevent_initial_call=True,
)
def entrar(_n, _s, usuario, senha):
    if not usuario or not senha:
        return c.msg("Informe usuário e senha.", "erro"), no_update
    status, u = auth.autenticar(usuario, senha)
    if status == "invalido":
        return c.msg("Usuário ou senha inválidos.", "erro"), no_update
    if status == "inativo":
        return c.msg("Este usuário está desativado. Procure um administrador.", "erro"), no_update
    auth.iniciar_sessao(u, senha)
    return no_update, "/"


# ---------------------------------------------------------------------------
# Estrutura (menu + conteúdo)
# ---------------------------------------------------------------------------

def menu(rota_atual: str, usuario: dict) -> list:
    itens, secao_atual = [], None
    for rota, (rotulo, secao, niveis, _) in PAGINAS.items():
        if secao is None or usuario.get("nivel") not in niveis:
            continue
        if secao != secao_atual:
            itens.append(html.Div(secao, className="menu-secao"))
            secao_atual = secao
        itens.append(dcc.Link(rotulo, href=rota, className="menu-link" + (" ativo" if rota == rota_atual else "")))
    return itens


def layout_app(usuario: dict) -> html.Div:
    logo = _logo_src()
    aviso = html.Div("Você ainda usa a senha padrão. Troque em “Minha senha”.", className="aviso-senha") \
        if usuario.get("senha_padrao") else None
    return html.Div([
        dcc.Location(id="url", refresh="callback-nav"),
        html.Nav([
            html.Img(src=logo, className="logo") if logo else None,
            html.Div(config.NOME_SISTEMA, className="sistema"),
            html.Div([html.B(usuario.get("nome")), html.Span(usuario.get("nivel"))], className="user-chip"),
            html.Div(id="menu"),
            html.Div([
                html.Div(id="aviso-senha", children=aviso),
                dcc.Link("Minha senha", href="/senha", className="menu-link"),
                html.A("Sair", href="/sair", className="menu-link"),
            ], className="menu-rodape"),
        ], className="sidebar"),
        html.Main(id="conteudo", className="conteudo"),
    ], className="shell")


def layout_raiz():
    """Roda a cada carga da página: sem login → tela de login."""
    try:
        crud.garantir_dados_padrao()
    except Exception as erro:  # banco sem tabelas
        log.exception("Falha ao preparar o banco")
        return html.Div(html.Div([
            html.H1("Banco de dados não preparado"),
            html.P("Na pasta do projeto, rode:  alembic upgrade head  e depois  python -m src.model.init_db"),
            html.P(f"Detalhe técnico: {erro}", style={"fontSize": ".8rem"}),
        ], className="login-caixa"), className="login-fundo")
    usuario = auth.usuario_atual(revalidar=True)
    return layout_app(usuario) if usuario else layout_login()


@callback(Output("conteudo", "children"), Output("menu", "children"), Input("url", "pathname"),
          State("url", "search"))
def trocar_tela(rota, busca):
    usuario = auth.usuario_atual(revalidar=True)
    if not usuario:
        return html.Div([c.msg("Sua sessão terminou.", "aviso"), html.A("Entrar novamente", href="/")]), []
    rota = rota if rota in PAGINAS else "/"
    _, _, niveis, montar = PAGINAS[rota]
    if usuario.get("nivel") not in niveis:
        return c.msg("Você não tem permissão para acessar esta tela.", "erro"), menu(rota, usuario)
    if rota == "/servidor" and busca:
        servidor = dict(p.split("=", 1) for p in busca.lstrip("?").split("&") if "=" in p).get("id")
        return montar(servidor), menu(rota, usuario)
    return montar(), menu(rota, usuario)


# ---------------------------------------------------------------------------
# Fábrica
# ---------------------------------------------------------------------------

def criar_app() -> Dash:
    app = Dash(
        __name__,
        title=config.NOME_SISTEMA,
        assets_folder=str(ASSETS),
        suppress_callback_exceptions=True,
        update_title=None,
    )
    server: flask.Flask = app.server
    server.secret_key = auth.chave_secreta()
    server.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

    @server.route("/sair")
    def sair():
        auth.encerrar_sessao()
        return flask.redirect("/")

    app.layout = layout_raiz
    app.index_string = app.index_string.replace("<html>", '<html lang="pt-BR">')
    return app
