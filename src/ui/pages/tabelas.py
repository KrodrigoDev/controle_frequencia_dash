"""Tabelas de apoio: status, cargos, segmentos... (somente administrador)."""

from __future__ import annotations

from dash import Input, Output, State, callback, ctx, dcc, html, no_update

from src.model import crud
from src.services import indicadores as ind
from src.ui import auth
from src.ui import componentes as c

P = "tab"
NOMES = {
    "status_presenca": "Status de presença",
    "cargo_funcao": "Cargo / função",
    "carga_horaria": "Carga horária",
    "tipo_professor": "Segmento do professor",
    "tipo_servidor": "Tipo de servidor",
    "formacao_academica": "Formação acadêmica",
    "tipo_vinculo": "Tipo de vínculo",
}


def layout():
    return html.Div([
        *c.cabecalho("Tabelas de apoio",
                     "Listas usadas nos formulários (cargos, segmentos, status...). Itens em uso não podem ser excluídos."),
        dcc.Store(id=f"{P}-versao", data=0),
        html.Div([html.Div([html.Label("Tabela"), dcc.Dropdown(
            id=f"{P}-chave", options=[{"label": v, "value": k} for k, v in NOMES.items()], value="cargo_funcao",
            clearable=False)], className="filtro")], className="filtros"),
        html.Div([
            c.bloco("Itens cadastrados", html.Div(id=f"{P}-lista")),
            c.bloco("Adicionar, renomear ou excluir", html.Div([
                html.Div([html.Label("Novo item"), dcc.Input(id=f"{P}-novo", type="text")], className="campo"),
                c.botao("Adicionar", f"{P}-add", "primario"),
                html.Hr(style={"border": 0, "borderTop": "1px solid #E3E8EF", "margin": "16px 0"}),
                html.Div([html.Label("Item"), dcc.Dropdown(id=f"{P}-item")], className="campo"),
                html.Div([html.Label("Novo nome"), dcc.Input(id=f"{P}-renome", type="text")], className="campo"),
                html.Div([c.botao("Renomear", f"{P}-ren"), c.botao("Excluir", f"{P}-del", "perigo")],
                         className="botoes"),
                html.Div(id=f"{P}-msg"),
            ]), sub="Os textos são gravados em MAIÚSCULAS, como no restante do sistema."),
        ], className="grade-2"),
    ])


@callback(Output(f"{P}-lista", "children"), Output(f"{P}-item", "options"), Output(f"{P}-item", "value"),
          Input(f"{P}-chave", "value"), Input(f"{P}-versao", "data"))
def lista(chave, _v):
    auth.exigir(auth.SOMENTE_ADMIN)
    opts = sorted(crud.lookup_options(chave).items(), key=lambda x: ind.chave_nome(x[1]))
    if not opts:
        return c.msg("Nenhum item cadastrado.", "info"), [], None
    import pandas as pd

    df = pd.DataFrame([{"valor": v, "uso": "Em uso" if crud.lookup_in_use(chave, i) else "—"} for i, v in opts])
    aviso = c.msg("Cuidado ao renomear COMPARECEU, FALTOU, ATESTADO ou DECLARAÇÃO: os indicadores usam esses "
                  "nomes (veja config.py). Status novos entram como “Outros”.", "aviso") \
        if chave == "status_presenca" else None
    return ([aviso, c.tabela(f"{P}-tabela", df, {"valor": NOMES[chave], "uso": "Uso"}, 25)],
            [{"label": v, "value": i} for i, v in opts], None)


@callback(Output(f"{P}-renome", "value"), Input(f"{P}-item", "value"), State(f"{P}-chave", "value"))
def preencher(item, chave):
    auth.exigir(auth.SOMENTE_ADMIN)
    return crud.lookup_options(chave).get(item, "") if item else ""


@callback(
    Output(f"{P}-msg", "children"), Output(f"{P}-versao", "data"), Output(f"{P}-novo", "value"),
    Input(f"{P}-add", "n_clicks"), Input(f"{P}-ren", "n_clicks"), Input(f"{P}-del", "n_clicks"),
    State(f"{P}-chave", "value"), State(f"{P}-novo", "value"), State(f"{P}-item", "value"),
    State(f"{P}-renome", "value"), State(f"{P}-versao", "data"),
    prevent_initial_call=True,
)
def acoes(_a, _r, _d, chave, novo, item, renome, versao):
    auth.exigir(auth.SOMENTE_ADMIN)
    existentes = {v.upper() for v in crud.lookup_options(chave).values()}
    gatilho = ctx.triggered_id
    if gatilho == f"{P}-add":
        valor = (novo or "").strip().upper()
        if not valor:
            return c.msg("Digite o novo item.", "erro"), no_update, no_update
        if valor in existentes:
            return c.msg(f"“{valor}” já existe.", "erro"), no_update, no_update
        crud.add_lookup(chave, valor)
        return c.msg(f"“{valor}” adicionado.", "ok"), (versao or 0) + 1, ""
    if not item:
        return c.msg("Escolha o item.", "erro"), no_update, no_update
    if gatilho == f"{P}-ren":
        valor = (renome or "").strip().upper()
        if not valor:
            return c.msg("Digite o novo nome.", "erro"), no_update, no_update
        if valor in existentes and valor != crud.lookup_options(chave).get(item, "").upper():
            return c.msg(f"“{valor}” já existe.", "erro"), no_update, no_update
        crud.update_lookup(chave, item, valor)
        return c.msg("Item renomeado.", "ok"), (versao or 0) + 1, no_update
    if gatilho == f"{P}-del":
        if crud.lookup_in_use(chave, item):
            return c.msg("Este item está em uso e não pode ser excluído.", "erro"), no_update, no_update
        crud.delete_lookup(chave, item)
        return c.msg("Item excluído.", "ok"), (versao or 0) + 1, no_update
    return no_update, no_update, no_update
