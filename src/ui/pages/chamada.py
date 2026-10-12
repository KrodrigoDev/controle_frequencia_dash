"""Fazer chamada: lança (ou corrige) a presença de um dia."""

from __future__ import annotations

import datetime as dt

from dash import Input, Output, State, callback, dash_table, dcc, html, no_update

import config
from src.model import crud
from src.services import indicadores as ind
from src.ui import auth
from src.ui import componentes as c

P = "ch"


def layout():
    ativos = crud.list_servidores(apenas_ativos=True)
    segmentos = sorted(ativos["tipo_professor"].dropna().unique(), key=ind.chave_nome) if not ativos.empty else []
    return html.Div([
        *c.cabecalho("Fazer chamada",
                     "1) Escolha o dia  2) Ajuste quem faltou ou trouxe atestado  3) Clique em Salvar chamada. "
                     "Se o dia já tiver chamada, ela aparece preenchida e pode ser corrigida."),
        c.msg("Nenhum servidor ativo cadastrado. Peça a um administrador para cadastrar.", "aviso")
        if ativos.empty else None,
        html.Div([
            html.Div([html.Label("Dia"),
                      dcc.DatePickerSingle(id=f"{P}-data", date=dt.date.today(), display_format="DD/MM/YYYY",
                                           first_day_of_week=0, max_date_allowed=dt.date.today())],
                     className="filtro", style={"maxWidth": "190px"}),
            html.Div([html.Label("Segmento (professores)"),
                      dcc.Dropdown(id=f"{P}-segmentos", options=segmentos, multi=True, placeholder="Todos")],
                     className="filtro"),
            html.Div([html.Label("Servidor(es)"),
                      dcc.Dropdown(id=f"{P}-nomes", multi=True, placeholder="Todos do filtro")],
                     className="filtro largo"),
        ], className="filtros"),
        html.Div(id=f"{P}-aviso-dia"),
        c.bloco(None, html.Div([
            c.botao("Todos compareceram", f"{P}-todos"),
            html.Span(id=f"{P}-contagem", className="sub", style={"color": "#6B7280", "fontSize": ".85rem"}),
        ], className="botoes", style={"marginBottom": "10px"}),
            dash_table.DataTable(
                id=f"{P}-tabela",
                columns=[
                    {"name": "Servidor", "id": "servidor", "editable": False},
                    {"name": "Cargo / função", "id": "cargo", "editable": False},
                    {"name": "Segmento", "id": "segmento", "editable": False},
                    {"name": "Já lançado?", "id": "lancado", "editable": False},
                    {"name": "Status (clique para mudar)", "id": "status", "presentation": "dropdown",
                     "editable": True},
                    {"name": "Observação", "id": "observacao", "editable": True},
                ],
                data=[], editable=True, page_action="none", sort_action="native",
                style_table={"overflowX": "auto", "maxHeight": "60vh", "overflowY": "auto"},
                fixed_rows={"headers": True},
                style_cell={"textAlign": "left", "minWidth": "90px", "whiteSpace": "normal", "height": "auto",
                            "fontFamily": c.FONTE, "fontSize": "13px", "padding": "6px 8px"},
                style_header={"backgroundColor": config.COR_PRIMARIA, "color": "#FFFFFF", "fontWeight": "600"},
                style_cell_conditional=[{"if": {"column_id": "servidor"}, "minWidth": "220px"},
                                        {"if": {"column_id": "status"}, "minWidth": "170px"},
                                        {"if": {"column_id": "observacao"}, "minWidth": "220px"}],
                style_data_conditional=[
                    {"if": {"filter_query": '{status} = "FALTOU"', "column_id": "status"},
                     "backgroundColor": "#F9E0E0", "fontWeight": "700"},
                    {"if": {"filter_query": '{status} = "ATESTADO" or {status} = "DECLARAÇÃO"', "column_id": "status"},
                     "backgroundColor": "#FDEFD9", "fontWeight": "700"},
                    {"if": {"filter_query": '{lancado} = "Não"', "column_id": "lancado"}, "color": "#B26B00"},
                ],
                css=[{"selector": ".Select-menu-outer", "rule": "display: block !important"}],
            ),
            html.Div([c.botao("Salvar chamada", f"{P}-salvar", "primario")], className="botoes",
                     style={"marginTop": "12px"}),
            html.Div(id=f"{P}-msg")),
        dcc.Store(id=f"{P}-salvo", data=0),
        html.Div(id=f"{P}-controle"),
    ])


@callback(Output(f"{P}-nomes", "options"), Input(f"{P}-segmentos", "value"))
def opcoes_nomes(segmentos):
    auth.exigir()
    ativos = crud.list_servidores(apenas_ativos=True)
    if ativos.empty:
        return []
    if segmentos:
        ativos = ativos[ativos["tipo_professor"].isin(segmentos)]
    return sorted(ativos["nome_servidor"], key=ind.chave_nome)


def _status_opcoes():
    return list(crud.lookup_options("status_presenca").values())


@callback(
    Output(f"{P}-tabela", "data"), Output(f"{P}-tabela", "dropdown"), Output(f"{P}-contagem", "children"),
    Output(f"{P}-aviso-dia", "children"),
    Input(f"{P}-data", "date"), Input(f"{P}-segmentos", "value"), Input(f"{P}-nomes", "value"),
    Input(f"{P}-salvo", "data"),
)
def carregar(data_txt, segmentos, nomes, _salvo):
    auth.exigir()
    if not data_txt:
        return [], no_update, "", c.msg("Escolha o dia.", "aviso")
    dia = dt.date.fromisoformat(data_txt[:10])
    ativos = crud.list_servidores(apenas_ativos=True)
    opcoes = _status_opcoes()
    padrao = next(iter(config.STATUS_PRESENTE & set(opcoes)), opcoes[0] if opcoes else "")
    if segmentos:
        ativos = ativos[ativos["tipo_professor"].isin(segmentos)]
    if nomes:
        ativos = ativos[ativos["nome_servidor"].isin(nomes)]
    ativos = ativos.sort_values("nome_servidor", key=lambda s: s.map(ind.chave_nome))
    ja = crud.presencas_do_dia(dia)
    rotulo = crud.lookup_options("status_presenca")
    linhas = [{
        "id_servidor": int(r.id), "servidor": r.nome_servidor, "cargo": c.valor(r.cargo_funcao) or "",
        "segmento": c.valor(r.tipo_professor) or "—", "lancado": "Sim" if r.id in ja else "Não",
        "status": rotulo.get(ja[r.id]["id_status_presenca"], padrao) if r.id in ja else padrao,
        "observacao": ja[r.id]["observacao"] if r.id in ja else "",
    } for r in ativos.itertuples()]
    n_ja = sum(1 for linha in linhas if linha["lancado"] == "Sim")
    contagem = f"{len(linhas)} servidor(es) na lista · {n_ja} já lançado(s) neste dia"
    avisos = []
    if dia.weekday() >= 5:
        avisos.append(c.msg(f"{ind.fmt_data(dia)} é {'sábado' if dia.weekday() == 5 else 'domingo'}. "
                            "Só lance se houve expediente.", "aviso"))
    if n_ja:
        avisos.append(c.msg(f"Este dia já tem chamada para {n_ja} servidor(es). Ao salvar, os dados serão corrigidos.",
                            "info"))
    return linhas, {"status": {"options": [{"label": o, "value": o} for o in opcoes], "clearable": False}}, \
        contagem, avisos


@callback(
    Output(f"{P}-tabela", "data", allow_duplicate=True),
    Input(f"{P}-todos", "n_clicks"), State(f"{P}-tabela", "data"), prevent_initial_call=True,
)
def todos_compareceram(_n, linhas):
    auth.exigir()
    opcoes = _status_opcoes()
    padrao = next(iter(config.STATUS_PRESENTE & set(opcoes)), None)
    if not padrao or not linhas:
        return no_update
    return [{**linha, "status": padrao} for linha in linhas]


@callback(
    Output(f"{P}-msg", "children"), Output(f"{P}-salvo", "data"),
    Input(f"{P}-salvar", "n_clicks"),
    State(f"{P}-tabela", "data"), State(f"{P}-data", "date"), State(f"{P}-salvo", "data"),
    prevent_initial_call=True,
)
def salvar(_n, linhas, data_txt, salvo):
    auth.exigir()
    if not linhas or not data_txt:
        return c.msg("Não há servidores na lista para salvar.", "aviso"), no_update
    dia = dt.date.fromisoformat(data_txt[:10])
    por_rotulo = {v: k for k, v in crud.lookup_options("status_presenca").items()}
    sem_status = [linha["servidor"] for linha in linhas if linha.get("status") not in por_rotulo]
    if sem_status:
        return c.msg("Escolha o status de: " + ", ".join(sem_status[:5]), "erro"), no_update
    crud.bulk_upsert_presenca(dia, [{
        "id_servidor": int(linha["id_servidor"]), "id_status_presenca": por_rotulo[linha["status"]],
        "observacao": (linha.get("observacao") or "").strip(),
    } for linha in linhas])
    faltas = sum(1 for linha in linhas if linha["status"] in config.STATUS_FALTA)
    return c.msg(f"Chamada de {ind.fmt_data(dia)} salva para {len(linhas)} servidor(es) "
                 f"({faltas} falta(s) sem justificativa).", "ok"), (salvo or 0) + 1


@callback(Output(f"{P}-controle", "children"), Input(f"{P}-data", "date"), Input(f"{P}-salvo", "data"))
def controle_do_dia(data_txt, _salvo):
    auth.exigir()
    if not data_txt:
        return None
    dia = dt.date.fromisoformat(data_txt[:10])
    ativos = crud.list_servidores(apenas_ativos=True)
    if ativos.empty:
        return None
    ja = crud.presencas_do_dia(dia)
    rotulo = crud.lookup_options("status_presenca")
    ativos = ativos.assign(lancado=ativos["id"].isin(list(ja)))
    total, feitos = len(ativos), int(ativos["lancado"].sum())
    faltas = sum(1 for i in ativos.loc[ativos["lancado"], "id"]
                 if rotulo.get(ja[int(i)]["id_status_presenca"]) in config.STATUS_FALTA)
    pend = ativos[~ativos["lancado"]].sort_values("nome_servidor", key=lambda s: s.map(ind.chave_nome))
    resumo_seg = (ativos.assign(segmento=ativos["tipo_professor"].fillna("Não é professor"))
                  .groupby("segmento").agg(servidores=("id", "count"), lancados=("lancado", "sum")).reset_index())
    resumo_seg["pendentes"] = resumo_seg["servidores"] - resumo_seg["lancados"]
    return c.bloco(f"Como está a chamada de {ind.fmt_data(dia)}", html.Div([
        c.kpi("Servidores ativos", total, "esperados na chamada"),
        c.kpi("Já lançados", feitos, f"{round(feitos / total * 100) if total else 0}% da chamada", config.COR_PRESENTE),
        c.kpi("Faltando lançar", total - feitos, "pendentes neste dia",
              config.COR_JUSTIFICADO if total - feitos else config.COR_PRESENTE),
        c.kpi("Faltas no dia", faltas, "sem justificativa", config.COR_FALTA),
    ], className="kpis"), html.Div([
        html.Div([html.H3("Por segmento", style={"fontSize": ".95rem"}),
                  c.tabela(f"{P}-seg", resumo_seg, {"segmento": "Segmento", "servidores": "Servidores",
                                                    "lancados": "Lançados", "pendentes": "Faltando"}, 20)]),
        html.Div([html.H3("Quem falta lançar", style={"fontSize": ".95rem"}),
                  c.tabela(f"{P}-pend", pend.fillna("—"), {"nome_servidor": "Servidor", "cargo_funcao": "Cargo / função",
                                                           "tipo_professor": "Segmento"}, 10)
                  if not pend.empty else c.msg("Todos os servidores ativos já têm registro neste dia.", "ok")]),
    ], className="grade-2"))
