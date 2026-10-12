"""Usuários do sistema (admin) e troca da própria senha (todos)."""

from __future__ import annotations

import flask
from dash import Input, Output, State, callback, dcc, html, no_update

import config
from src.model import crud
from src.ui import auth
from src.ui import componentes as c

P = "usr"
NOVO = "novo"


def _opcoes_usuarios():
    df = crud.list_usuarios()
    return [{"label": "+ Criar novo usuário", "value": NOVO}] + [
        {"label": f"{r.username} — {r.nome}" + ("" if r.ativo else " (desativado)"), "value": int(r.id)}
        for r in df.itertuples()]


def _opcoes_nivel():
    return [{"label": config.NIVEIS_ACESSO.get(n, n), "value": i} for i, n in crud.list_niveis().items()]


def layout():
    return html.Div([
        *c.cabecalho("Usuários", "Quem pode entrar no sistema. Administrador: acesso total. "
                                 "Operador: faz a chamada, acompanha e exporta relatórios."),
        dcc.Store(id=f"{P}-versao", data=0),
        html.Div([
            c.bloco("Usuários cadastrados", html.Div(id=f"{P}-lista")),
            c.bloco("Criar ou editar", html.Div([
                html.Div([html.Label("Usuário"), dcc.Dropdown(id=f"{P}-sel", options=_opcoes_usuarios(), value=NOVO,
                                                              clearable=False)], className="campo"),
                html.Div([
                    html.Div([html.Label("Login *"), dcc.Input(id=f"{P}-login", type="text")], className="campo"),
                    html.Div([html.Label("Nome completo *"), dcc.Input(id=f"{P}-nome", type="text")], className="campo"),
                ], className="form-grade"),
                html.Div([html.Label("Nível de acesso"), dcc.Dropdown(id=f"{P}-nivel", options=_opcoes_nivel(),
                                                                      clearable=False)], className="campo"),
                dcc.Checklist(id=f"{P}-ativo", options=[{"label": " Ativo (pode entrar no sistema)", "value": "s"}],
                              value=["s"], style={"marginBottom": "10px"}),
                html.Div([
                    html.Div([html.Label(id=f"{P}-senha-rot"), dcc.Input(id=f"{P}-senha", type="password")],
                             className="campo"),
                    html.Div([html.Label("Confirmar senha"), dcc.Input(id=f"{P}-senha2", type="password")],
                             className="campo"),
                ], className="form-grade"),
                html.Div([c.botao("Salvar", f"{P}-salvar", "primario")], className="botoes"),
                html.Div(id=f"{P}-msg"),
            ])),
        ], className="grade-2"),
    ])


@callback(Output(f"{P}-lista", "children"), Input(f"{P}-versao", "data"))
def lista(_v):
    auth.exigir(auth.SOMENTE_ADMIN)
    df = crud.list_usuarios()
    df = df.assign(ativo=df["ativo"].map({True: "Sim", False: "Não"}))
    return c.tabela(f"{P}-tabela", df, {"username": "Login", "nome": "Nome", "nivel_acesso": "Nível",
                                        "ativo": "Ativo"}, 20)


@callback(
    Output(f"{P}-login", "value"), Output(f"{P}-login", "disabled"), Output(f"{P}-nome", "value"),
    Output(f"{P}-nivel", "value"), Output(f"{P}-ativo", "value"), Output(f"{P}-senha-rot", "children"),
    Output(f"{P}-senha", "value"), Output(f"{P}-senha2", "value"),
    Input(f"{P}-sel", "value"), Input(f"{P}-versao", "data"),
)
def carregar(sel, _v):
    auth.exigir(auth.SOMENTE_ADMIN)
    if sel in (None, NOVO):
        operador = next((i for i, n in crud.list_niveis().items() if n == config.NIVEL_OPERADOR), None)
        return "", False, "", operador, ["s"], f"Senha * (mínimo {config.SENHA_MINIMA})", "", ""
    u = crud.get_usuario(int(sel))
    return (u["username"], True, u["nome"], u["id_nivel_acesso"], ["s"] if u["ativo"] else [],
            "Nova senha (deixe em branco para não mudar)", "", "")


@callback(
    Output(f"{P}-msg", "children"), Output(f"{P}-versao", "data"), Output(f"{P}-sel", "options"),
    Output(f"{P}-sel", "value"),
    Input(f"{P}-salvar", "n_clicks"),
    State(f"{P}-sel", "value"), State(f"{P}-login", "value"), State(f"{P}-nome", "value"),
    State(f"{P}-nivel", "value"), State(f"{P}-ativo", "value"), State(f"{P}-senha", "value"),
    State(f"{P}-senha2", "value"), State(f"{P}-versao", "data"),
    prevent_initial_call=True,
)
def salvar(_n, sel, login, nome, nivel, ativo, senha, senha2, versao):
    eu = auth.exigir(auth.SOMENTE_ADMIN)
    sem_mudanca = (no_update, no_update, no_update)
    if (senha or senha2) and senha != senha2:
        return c.msg("As senhas não conferem.", "erro"), *sem_mudanca
    try:
        if sel in (None, NOVO):
            novo_id = crud.add_usuario(login or "", nome or "", senha or "", nivel)
            texto, sel = f"Usuário “{(login or '').strip().lower()}” criado.", novo_id
        else:
            nivel_nome = crud.list_niveis().get(nivel)
            if int(sel) == eu["uid"] and (not ativo or nivel_nome != config.NIVEL_ADMIN):
                return c.msg("Você não pode desativar nem rebaixar o seu próprio usuário.", "erro"), *sem_mudanca
            if not (nome or "").strip():
                return c.msg("Informe o nome.", "erro"), *sem_mudanca
            crud.update_usuario(int(sel), nome, nivel, bool(ativo))
            texto = "Usuário atualizado."
            if senha:
                crud.alterar_senha(int(sel), senha)
                texto += " Senha redefinida."
                if int(sel) == eu["uid"]:
                    flask.session["senha_padrao"] = False
    except ValueError as erro:
        return c.msg(str(erro), "erro"), *sem_mudanca
    return c.msg(texto, "ok"), (versao or 0) + 1, _opcoes_usuarios(), sel


# ---------------------------------------------------------------------------
# Minha senha (qualquer usuário logado)
# ---------------------------------------------------------------------------

def layout_minha_senha():
    return html.Div([
        *c.cabecalho("Minha senha", f"Troque a sua senha de acesso. Mínimo de {config.SENHA_MINIMA} caracteres."),
        c.bloco(None, html.Div([
            html.Div([html.Label("Senha atual"), dcc.Input(id="ms-atual", type="password")], className="campo"),
            html.Div([html.Label("Nova senha"), dcc.Input(id="ms-nova", type="password")], className="campo"),
            html.Div([html.Label("Confirmar nova senha"), dcc.Input(id="ms-conf", type="password")], className="campo"),
            c.botao("Alterar senha", "ms-salvar", "primario"),
            html.Div(id="ms-msg"),
        ]), style={"maxWidth": "420px"}),
    ])


@callback(Output("ms-msg", "children"), Output("ms-atual", "value"), Output("ms-nova", "value"),
          Output("ms-conf", "value"), Input("ms-salvar", "n_clicks"),
          State("ms-atual", "value"), State("ms-nova", "value"), State("ms-conf", "value"), prevent_initial_call=True)
def trocar_senha(_n, atual, nova, conf):
    eu = auth.exigir()
    status, _ = auth.autenticar(eu["username"], atual or "")
    if status != "ok":
        return c.msg("Senha atual incorreta.", "erro"), "", no_update, no_update
    if nova != conf:
        return c.msg("As senhas novas não conferem.", "erro"), no_update, "", ""
    try:
        crud.alterar_senha(eu["uid"], nova or "")
    except ValueError as erro:
        return c.msg(str(erro), "erro"), no_update, no_update, no_update
    flask.session["senha_padrao"] = False
    return c.msg("Senha alterada com sucesso.", "ok"), "", "", ""
