"""Cadastro de servidores (somente administrador)."""

from __future__ import annotations

from dash import Input, Output, State, callback, ctx, dcc, html, no_update

from src.model import crud
from src.services import exportar_excel as xls
from src.services import indicadores as ind
from src.ui import auth
from src.ui import componentes as c

P = "srv"
NOVO = "novo"

CAMPOS_LOOKUP = [  # (campo no banco, tabela de apoio, rótulo, pode ficar vazio?)
    ("id_tipo_vinculo", "tipo_vinculo", "Tipo de vínculo", False),
    ("id_cargo_funcao", "cargo_funcao", "Cargo / função", False),
    ("id_carga_horaria", "carga_horaria", "Carga horária", False),
    ("id_tipo_servidor", "tipo_servidor", "Tipo de servidor", False),
    ("id_tipo_professor", "tipo_professor", "Segmento (se for professor)", True),
    ("id_formacao_academica", "formacao_academica", "Formação acadêmica", True),
]
COLS_LISTA = {"nome_servidor": "Servidor", "matricula": "Matrícula", "cargo_funcao": "Cargo / função",
              "tipo_professor": "Segmento", "tipo_servidor": "Tipo", "tipo_vinculo": "Vínculo",
              "carga_horaria": "CH", "situacao": "Situação"}


def _opcoes_select():
    return [{"label": "+ Cadastrar novo servidor", "value": NOVO}, *c.opcoes_servidores()]


def layout():
    campos = [
        html.Div([html.Label(rot + ("" if vazio else " *")),
                  dcc.Dropdown(id=f"{P}-{campo}", clearable=vazio,
                               options=[{"label": v, "value": k} for k, v in
                                        sorted(crud.lookup_options(tabela).items(), key=lambda x: ind.chave_nome(x[1]))])],
                 className="campo")
        for campo, tabela, rot, vazio in CAMPOS_LOOKUP
    ]
    return html.Div([
        *c.cabecalho("Servidores", "Cadastre, edite ou desligue servidores. Desligar mantém o histórico de presença."),
        dcc.Store(id=f"{P}-versao", data=0),
        dcc.Download(id=f"{P}-download"),
        html.Div([
            c.bloco("Lista de servidores", html.Div([
                html.Div([html.Label("Buscar"), dcc.Input(id=f"{P}-busca", type="text", debounce=True,
                                                          placeholder="Nome ou matrícula")], className="filtro"),
                html.Div([dcc.Checklist(id=f"{P}-inativos", options=[{"label": " Mostrar desligados",
                                                                       "value": "s"}], value=[])],
                         className="filtro", style={"paddingBottom": "8px"}),
                c.botao("Baixar Excel", f"{P}-xlsx", "exportar"),
            ], className="filtros"), html.Div(id=f"{P}-lista"),
                sub="Clique numa linha para editar."),
            c.bloco("Dados do servidor", html.Div([
                html.Div([html.Label("Editar"), dcc.Dropdown(id=f"{P}-sel", options=_opcoes_select(), value=NOVO,
                                                             clearable=False)], className="campo"),
                html.Div([html.Label("Nome *"), dcc.Input(id=f"{P}-nome", type="text")], className="campo"),
                html.Div([
                    html.Div([html.Label("Matrícula"), dcc.Input(id=f"{P}-matricula", type="text")], className="campo"),
                    html.Div([html.Label("CPF"), dcc.Input(id=f"{P}-cpf", type="text")], className="campo"),
                ], className="form-grade"),
                html.Div(campos, className="form-grade"),
                html.Div([c.botao("Salvar", f"{P}-salvar", "primario"),
                          c.botao("Desligar", f"{P}-alternar", "perigo"),
                          c.botao("Excluir definitivamente", f"{P}-excluir", "perigo")], className="botoes"),
                html.Div(id=f"{P}-msg"),
            ])),
        ], className="grade-2-1"),
    ])


@callback(Output(f"{P}-lista", "children"), Input(f"{P}-busca", "value"), Input(f"{P}-inativos", "value"),
          Input(f"{P}-versao", "data"))
def lista(busca, inativos, _v):
    auth.exigir(auth.SOMENTE_ADMIN)
    df = crud.list_servidores(apenas_ativos=not inativos)
    if df.empty:
        return c.msg("Nenhum servidor cadastrado. Use o formulário ao lado.", "info")
    if busca:
        b = ind.chave_nome(busca)
        df = df[df["nome_servidor"].map(ind.chave_nome).str.contains(b, regex=False)
                | df["matricula"].fillna("").astype(str).str.contains(busca, regex=False)]
    df = df.assign(situacao=df["ativo"].map({True: "Ativo", False: "Desligado"})) \
        .sort_values("nome_servidor", key=lambda s: s.map(ind.chave_nome)).fillna("")
    return [html.P(f"{len(df)} servidor(es)", className="sub"),
            c.tabela(f"{P}-tabela", df, {"id": "id", **COLS_LISTA}, 15, hidden_columns=["id"],
                     css=[{"selector": ".show-hide", "rule": "display: none"}],
                     style_data_conditional=[{"if": {"filter_query": '{situacao} = "Desligado"'}, "color": "#9AA3AF"}])]


@callback(Output(f"{P}-sel", "value", allow_duplicate=True), Input(f"{P}-tabela", "active_cell"),
          State(f"{P}-tabela", "derived_viewport_data"), prevent_initial_call=True)
def clicar_linha(celula, dados):
    auth.exigir(auth.SOMENTE_ADMIN)
    if not celula or not dados:
        return no_update
    return dados[celula["row"]]["id"]


@callback(
    Output(f"{P}-nome", "value"), Output(f"{P}-matricula", "value"), Output(f"{P}-cpf", "value"),
    *[Output(f"{P}-{campo}", "value") for campo, *_ in CAMPOS_LOOKUP],
    Output(f"{P}-alternar", "children"), Output(f"{P}-alternar", "style"), Output(f"{P}-excluir", "style"),
    Input(f"{P}-sel", "value"), Input(f"{P}-versao", "data"),
)
def carregar(sel, _v):
    auth.exigir(auth.SOMENTE_ADMIN)
    esconder = {"display": "none"}
    if sel in (None, NOVO):
        return ("", "", "", *[None] * len(CAMPOS_LOOKUP), "Desligar", esconder, esconder)
    s = crud.get_servidor(int(sel))
    if s is None:
        return ("", "", "", *[None] * len(CAMPOS_LOOKUP), "Desligar", esconder, esconder)
    tem_presenca = crud.servidor_tem_presencas(int(sel))
    return (s["nome_servidor"], s["matricula"] or "", s["cpf"] or "",
            *[s.get(campo) for campo, *_ in CAMPOS_LOOKUP],
            "Desligar" if s["ativo"] else "Reativar", {}, esconder if tem_presenca else {})


@callback(
    Output(f"{P}-msg", "children"), Output(f"{P}-versao", "data"), Output(f"{P}-sel", "options"),
    Output(f"{P}-sel", "value"),
    Input(f"{P}-salvar", "n_clicks"), Input(f"{P}-alternar", "n_clicks"), Input(f"{P}-excluir", "n_clicks"),
    State(f"{P}-sel", "value"), State(f"{P}-nome", "value"), State(f"{P}-matricula", "value"),
    State(f"{P}-cpf", "value"), *[State(f"{P}-{campo}", "value") for campo, *_ in CAMPOS_LOOKUP],
    State(f"{P}-versao", "data"),
    prevent_initial_call=True,
)
def acoes(_s, _a, _e, sel, nome, matricula, cpf, *resto):
    auth.exigir(auth.SOMENTE_ADMIN)
    *lookups, versao = resto
    gatilho = ctx.triggered_id
    novo_sel = sel
    if gatilho == f"{P}-salvar":
        nome = (nome or "").strip().upper()
        faltando = [rot for (campo, _, rot, vazio), v in zip(CAMPOS_LOOKUP, lookups) if not vazio and not v]
        if not nome:
            return c.msg("Informe o nome do servidor.", "erro"), no_update, no_update, no_update
        if faltando:
            return c.msg("Preencha: " + ", ".join(faltando) + ".", "erro"), no_update, no_update, no_update
        dados = {"nome_servidor": nome, "matricula": (matricula or "").strip(), "cpf": (cpf or "").strip(),
                 **{campo: v for (campo, *_), v in zip(CAMPOS_LOOKUP, lookups)}}
        if sel in (None, NOVO):
            novo_sel = crud.add_servidor(dados)
            texto = f"Servidor {nome} cadastrado."
        else:
            crud.update_servidor(int(sel), dados)
            texto = "Alterações salvas."
    elif gatilho == f"{P}-alternar" and sel not in (None, NOVO):
        s = crud.get_servidor(int(sel))
        crud.update_servidor(int(sel), {"ativo": not s["ativo"]})
        texto = ("Servidor desligado. O histórico de presença foi mantido e ele não aparece mais na chamada."
                 if s["ativo"] else "Servidor reativado. Ele volta a aparecer na chamada.")
    elif gatilho == f"{P}-excluir" and sel not in (None, NOVO):
        if crud.servidor_tem_presencas(int(sel)):
            return c.msg("Não é possível excluir: já há presenças lançadas. Use Desligar.", "erro"), \
                no_update, no_update, no_update
        crud.delete_servidor(int(sel), hard=True)
        texto, novo_sel = "Servidor excluído.", NOVO
    else:
        return no_update, no_update, no_update, no_update
    return c.msg(texto, "ok"), (versao or 0) + 1, _opcoes_select(), novo_sel


@callback(Output(f"{P}-download", "data"), Input(f"{P}-xlsx", "n_clicks"), prevent_initial_call=True)
def baixar(_n):
    auth.exigir(auth.SOMENTE_ADMIN)
    df = crud.list_servidores().sort_values("nome_servidor", key=lambda s: s.map(ind.chave_nome))
    df = df.assign(ativo=df["ativo"].map({True: "Ativo", False: "Desligado"})).rename(columns={
        "nome_servidor": "Servidor", "matricula": "Matrícula", "cpf": "CPF", "tipo_vinculo": "Vínculo",
        "cargo_funcao": "Cargo / função", "carga_horaria": "Carga horária", "tipo_servidor": "Tipo",
        "tipo_professor": "Segmento", "formacao_academica": "Formação", "ativo": "Situação"})
    return dcc.send_bytes(xls.excel_tabela("Servidores", df), "cadastro_servidores.xlsx")
