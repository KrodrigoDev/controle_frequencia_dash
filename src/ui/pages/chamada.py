"""Fazer chamada: lança (ou corrige) a presença de um dia."""

from __future__ import annotations

import datetime as dt

from dash import ALL, Input, Output, State, callback, dcc, html, no_update

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
                     "1) Escolha o dia  2) Clique no status de quem faltou ou trouxe atestado  3) Clique em Salvar chamada. "
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
            html.Div(id=f"{P}-lista", className="chamada"),
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
    """Status na ordem de uso: Compareceu, Faltou, Atestado/Declaração, outros."""
    ordem = {config.GRUPO_PRESENTE: 0, config.GRUPO_FALTA: 1, config.GRUPO_JUSTIFICADO: 2}
    return sorted(crud.lookup_options("status_presenca").values(),
                  key=lambda st: (ordem.get(ind.grupo_do_status(st), 3), st))


def _classe_status(status: str) -> str:
    grupo = ind.grupo_do_status(status)
    return {config.GRUPO_PRESENTE: "p", config.GRUPO_FALTA: "f", config.GRUPO_JUSTIFICADO: "j"}.get(grupo, "o")


def _linha(r, status: str, observacao: str, lancado: bool, opcoes: list[str]) -> html.Div:
    """Uma linha da chamada: nome + botões de status (um clique) + observação."""
    sid = int(r.id)
    detalhe = " · ".join(x for x in [c.valor(r.cargo_funcao), c.valor(r.tipo_professor)] if x)
    return html.Div([
        html.Div([
            html.Div(r.nome_servidor, className="ch-nome"),
            html.Div([detalhe, html.Span(" · já lançado" if lancado else " · ainda não lançado",
                                         className="ch-ok" if lancado else "ch-pend")], className="ch-detalhe"),
        ], className="ch-pessoa"),
        dcc.RadioItems(
            id={"tipo": f"{P}-st", "sid": sid}, value=status, inline=True, className="ch-status",
            options=[{"label": html.Span(o.capitalize(), className=f"pill {_classe_status(o)}"), "value": o}
                     for o in opcoes],
        ),
        dcc.Input(id={"tipo": f"{P}-obs", "sid": sid}, type="text", value=observacao, debounce=True,
                  placeholder="Observação (opcional)", className="ch-obs"),
    ], className="ch-linha")


@callback(
    Output(f"{P}-lista", "children"), Output(f"{P}-contagem", "children"), Output(f"{P}-aviso-dia", "children"),
    Input(f"{P}-data", "date"), Input(f"{P}-segmentos", "value"), Input(f"{P}-nomes", "value"),
    Input(f"{P}-salvo", "data"),
)
def carregar(data_txt, segmentos, nomes, _salvo):
    auth.exigir()
    if not data_txt:
        return [], "", c.msg("Escolha o dia.", "aviso")
    dia = dt.date.fromisoformat(data_txt[:10])
    ativos = crud.list_servidores(apenas_ativos=True)
    if ativos.empty:
        return [], "", None
    opcoes = _status_opcoes()
    padrao = next(iter(config.STATUS_PRESENTE & set(opcoes)), opcoes[0] if opcoes else None)
    if segmentos:
        ativos = ativos[ativos["tipo_professor"].isin(segmentos)]
    if nomes:
        ativos = ativos[ativos["nome_servidor"].isin(nomes)]
    ativos = ativos.sort_values("nome_servidor", key=lambda s: s.map(ind.chave_nome))
    ja = crud.presencas_do_dia(dia)
    rotulo = crud.lookup_options("status_presenca")
    linhas = []
    for r in ativos.itertuples():
        reg = ja.get(int(r.id))
        status = rotulo.get(reg["id_status_presenca"], padrao) if reg else padrao
        linhas.append(_linha(r, status, reg["observacao"] if reg else "", bool(reg), opcoes))
    n_ja = sum(1 for r in ativos.itertuples() if int(r.id) in ja)
    contagem = f"{len(linhas)} servidor(es) na lista · {n_ja} já lançado(s) neste dia"
    avisos = []
    if dia.weekday() >= 5:
        avisos.append(c.msg(f"{ind.fmt_data(dia)} é {'sábado' if dia.weekday() == 5 else 'domingo'}. "
                            "Só lance se houve expediente.", "aviso"))
    if n_ja:
        avisos.append(c.msg(f"Este dia já tem chamada para {n_ja} servidor(es). Ao salvar, os dados serão corrigidos.",
                            "info"))
    if not linhas:
        linhas = [c.msg("Nenhum servidor para os filtros escolhidos.", "info")]
    return linhas, contagem, avisos


@callback(
    Output({"tipo": f"{P}-st", "sid": ALL}, "value", allow_duplicate=True),
    Input(f"{P}-todos", "n_clicks"), State({"tipo": f"{P}-st", "sid": ALL}, "value"), prevent_initial_call=True,
)
def todos_compareceram(_n, valores):
    auth.exigir()
    padrao = next(iter(config.STATUS_PRESENTE & set(_status_opcoes())), None)
    if not padrao or not valores:
        return [no_update] * len(valores or [])
    return [padrao] * len(valores)


@callback(
    Output(f"{P}-msg", "children"), Output(f"{P}-salvo", "data"),
    Input(f"{P}-salvar", "n_clicks"),
    State({"tipo": f"{P}-st", "sid": ALL}, "value"), State({"tipo": f"{P}-st", "sid": ALL}, "id"),
    State({"tipo": f"{P}-obs", "sid": ALL}, "value"), State({"tipo": f"{P}-obs", "sid": ALL}, "id"),
    State(f"{P}-data", "date"), State(f"{P}-salvo", "data"),
    prevent_initial_call=True,
)
def salvar(_n, status, ids_st, obs, ids_obs, data_txt, salvo):
    auth.exigir()
    if not status or not data_txt:
        return c.msg("Não há servidores na lista para salvar.", "aviso"), no_update
    dia = dt.date.fromisoformat(data_txt[:10])
    por_rotulo = {v: k for k, v in crud.lookup_options("status_presenca").items()}
    observacoes = {i["sid"]: (o or "").strip() for i, o in zip(ids_obs, obs)}
    if any(s not in por_rotulo for s in status):
        return c.msg("Escolha o status de todos os servidores da lista.", "erro"), no_update
    crud.bulk_upsert_presenca(dia, [
        {"id_servidor": int(i["sid"]), "id_status_presenca": por_rotulo[s], "observacao": observacoes.get(i["sid"], "")}
        for i, s in zip(ids_st, status)
    ])
    faltas = sum(1 for s in status if s in config.STATUS_FALTA)
    return c.msg(f"Chamada de {ind.fmt_data(dia)} salva para {len(status)} servidor(es) "
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
