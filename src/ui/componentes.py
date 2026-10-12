"""Peças visuais reutilizadas pelas telas (cartões, filtros, tabelas, gráficos)."""

from __future__ import annotations

import datetime as dt

import pandas as pd
import plotly.graph_objects as go
from dash import dash_table, dcc, html

import config
from src.model import crud
from src.services import indicadores as ind

FONTE = '"Segoe UI", system-ui, -apple-system, Roboto, Arial, sans-serif'

# ---------------------------------------------------------------------------
# Textos e blocos
# ---------------------------------------------------------------------------


def cabecalho(titulo: str, ajuda: str = "") -> list:
    itens = [html.H1(titulo, className="pagina-titulo")]
    if ajuda:
        itens.append(html.P(ajuda, className="pagina-ajuda"))
    return itens


def bloco(titulo: str | None, *filhos, sub: str | None = None, **kw) -> html.Div:
    topo = []
    if titulo:
        topo.append(html.H3(titulo))
    if sub:
        topo.append(html.P(sub, className="sub"))
    return html.Div([*topo, *filhos], className="bloco", **kw)


def msg(texto, tipo: str = "info") -> html.Div:
    """tipo: ok | erro | aviso | info"""
    return html.Div(texto, className=f"msg {tipo}")


def kpi(rotulo: str, valor, detalhe: str = "", cor: str = config.COR_PRIMARIA) -> html.Div:
    return html.Div([
        html.Div(rotulo, className="rotulo"),
        html.Div(str(valor), className="valor"),
        html.Div(detalhe, className="detalhe"),
    ], className="kpi", style={"--accent": cor})


def kpis_resumo(res: dict, n_atencao: int, n_pend: int | None = None) -> html.Div:
    itens = [
        kpi("% de presença", ind.fmt_pct(res["pct_presenca"]),
            f"{res['presencas']} presenças em {res['registros']} dias registrados", config.COR_PRIMARIA),
        kpi("Faltas sem justificativa", res["faltas"], ind.fmt_pct(res["pct_falta"]) + " dos registros",
            config.COR_FALTA),
        kpi("Faltas justificadas", res["justificadas"], "atestados e declarações", config.COR_JUSTIFICADO),
        kpi("Servidores em atenção", n_atencao, f"{config.LIMITE_ALERTA_FALTAS}+ faltas sem justificativa",
            config.COR_FALTA if n_atencao else config.COR_PRESENTE),
    ]
    if n_pend is not None:
        itens.append(kpi("Lançamentos pendentes", n_pend, "ativo sem registro em dia com chamada",
                         config.COR_JUSTIFICADO if n_pend else config.COR_PRESENTE))
    return html.Div(itens, className="kpis")


def resumo_frases(frases: list[str]) -> html.Div:
    return html.Div(html.Ul([html.Li(f) for f in frases]), className="resumo")


def botao(texto: str, id_, tipo: str = "", **kw) -> html.Button:
    return html.Button(texto, id=id_, className=f"btn {tipo}".strip(), n_clicks=0, **kw)


# ---------------------------------------------------------------------------
# Filtros
# ---------------------------------------------------------------------------


def opcoes_periodo(apenas_meses: bool = False) -> tuple[list[dict], str]:
    """Opções do seletor de período e o valor padrão (mês atual)."""
    primeira, ultima = crud.periodo_com_dados()
    opcoes = ind.opcoes_periodo(primeira, ultima, incluir_anos=not apenas_meses)
    hoje = dt.date.today()
    return opcoes, f"m:{hoje.year}-{hoje.month:02d}"


def filtro_periodo(id_, apenas_meses: bool = False, rotulo: str = "Período") -> html.Div:
    opcoes, padrao = opcoes_periodo(apenas_meses)
    return html.Div([html.Label(rotulo), dcc.Dropdown(id=id_, options=opcoes, value=padrao, clearable=False)],
                    className="filtro")


def opcoes_dimensao(coluna: str) -> list[dict]:
    """Valores existentes de uma dimensão (cargo, segmento...) no cadastro."""
    df = crud.list_servidores()
    if df.empty or coluna not in df:
        return []
    valores = sorted(df[coluna].fillna("Não informado").unique(), key=ind.chave_nome)
    return [{"label": v, "value": v} for v in valores]


def filtros_dimensoes(prefixo: str, dimensoes: list[str] | None = None) -> list[html.Div]:
    """Um dropdown múltiplo por dimensão. Vazio = todos."""
    dimensoes = dimensoes or list(ind.DIMENSOES)
    return [
        html.Div([html.Label(rotulo),
                  dcc.Dropdown(id={"tipo": f"{prefixo}-dim", "col": ind.DIMENSOES[rotulo]},
                               options=opcoes_dimensao(ind.DIMENSOES[rotulo]), multi=True, placeholder="Todos")],
                 className="filtro")
        for rotulo in dimensoes
    ]


def filtros_de_valores(ids: list[dict], valores: list) -> dict:
    return {i["col"]: v for i, v in zip(ids or [], valores or []) if v}


def opcoes_servidores(apenas_ativos: bool = False) -> list[dict]:
    df = crud.list_servidores(apenas_ativos=apenas_ativos)
    if df.empty:
        return []
    df = df.sort_values("nome_servidor", key=lambda s: s.map(ind.chave_nome))
    return [{"label": f"{r.nome_servidor}" + (f" ({r.matricula})" if r.matricula else "")
             + ("" if r.ativo else " — desligado"), "value": int(r.id)} for r in df.itertuples()]


# ---------------------------------------------------------------------------
# Tabelas
# ---------------------------------------------------------------------------

ESTILO_SITUACAO = [
    {"if": {"filter_query": '{situacao} = "Atenção"', "column_id": "situacao"},
     "color": config.COR_FALTA, "fontWeight": "700"},
    {"if": {"filter_query": '{situacao} = "Em dia"', "column_id": "situacao"}, "color": config.COR_PRESENTE},
]


def tabela(id_, df: pd.DataFrame, colunas: dict[str, str], page_size: int = 15, **kw) -> dash_table.DataTable:
    """DataTable padrão. `colunas` = {coluna_do_df: título}."""
    cond = kw.pop("style_data_conditional", [])
    return dash_table.DataTable(
        id=id_,
        columns=[{"name": t, "id": c} for c, t in colunas.items()],
        data=df[list(colunas)].to_dict("records") if not df.empty else [],
        page_size=page_size,
        sort_action=kw.pop("sort_action", "native"),
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "whiteSpace": "normal", "height": "auto", "minWidth": "60px",
                    "fontFamily": FONTE, "fontSize": "13px", "padding": "6px 8px"},
        style_header={"backgroundColor": config.COR_PRIMARIA, "color": "#FFFFFF", "fontWeight": "600"},
        style_data_conditional=[{"if": {"row_index": "odd"}, "backgroundColor": "#F7F9FC"}, *cond],
        **kw,
    )


def valor(x):
    """None no lugar de NaN/None/'' (para montar textos)."""
    return None if x is None or (isinstance(x, float) and pd.isna(x)) or x == "" else x


def df_para_tela(df: pd.DataFrame) -> pd.DataFrame:
    """Datas em dd/mm/aaaa e % com vírgula, para exibir."""
    df = df.copy()
    if "data" in df:
        df["data"] = df["data"].map(lambda d: ind.fmt_data(d) if isinstance(d, dt.date) else d)
    if "pct_presenca" in df:
        df["pct_presenca"] = df["pct_presenca"].map(ind.fmt_pct)
    return df.fillna("")


COLS_SERVIDOR = {
    "nome_servidor": "Servidor", "cargo_funcao": "Cargo / função", "tipo_professor": "Segmento",
    "registros": "Dias registrados", "presencas": "Presenças", "faltas": "Faltas sem justif.",
    "justificadas": "Faltas justif.", "pct_presenca": "% presença", "situacao": "Situação",
}


def tabela_servidores(id_, ps: pd.DataFrame, page_size: int = 15) -> dash_table.DataTable:
    """Tabela "por servidor". Clicar numa linha abre a tela Por servidor (ver ligar_tabela_ao_individual)."""
    return tabela(id_, df_para_tela(ps), {"id_servidor": "id", **COLS_SERVIDOR}, page_size,
                  filter_action="native", hidden_columns=["id_servidor"],
                  css=[{"selector": ".show-hide", "rule": "display: none"},
                       {"selector": "td.dash-cell", "rule": "cursor: pointer"}],
                  style_data_conditional=ESTILO_SITUACAO, style_filter={"backgroundColor": "#FBFCFE"})


def ligar_tabela_ao_individual(id_tabela: str) -> None:
    """Registra: clicar numa linha da tabela → abre Por servidor daquela pessoa."""
    from dash import Input, Output, State, callback, no_update

    @callback(Output("url", "href", allow_duplicate=True), Input(id_tabela, "active_cell"),
              State(id_tabela, "derived_viewport_data"), State(id_tabela, "id"), prevent_initial_call=True)
    def _abrir(celula, dados, _id):
        if not celula or not dados:
            return no_update
        return f"/servidor?id={dados[celula['row']]['id_servidor']}"


# ---------------------------------------------------------------------------
# Gráficos (plotly)
# ---------------------------------------------------------------------------

def _layout_base(fig: go.Figure, altura: int = 320) -> go.Figure:
    fig.update_layout(
        height=altura, margin=dict(l=8, r=8, t=8, b=8), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#FFFFFF",
        font=dict(family="Segoe UI, system-ui, sans-serif", size=12, color="#1F2937"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title=None, traceorder="normal"),
        hoverlabel=dict(bgcolor="#FFFFFF", font_size=12), bargap=0.25,
    )
    fig.update_xaxes(showgrid=False, linecolor="#D6DCE5", tickfont=dict(color="#6B7280"))
    fig.update_yaxes(gridcolor="#EEF1F5", zeroline=False, tickfont=dict(color="#6B7280"))
    return fig


def grafico(fig: go.Figure | None, vazio: str = "Sem dados para o período.") -> html.Div | dcc.Graph:
    if fig is None:
        return msg(vazio, "info")
    return dcc.Graph(figure=fig, config={"displayModeBar": False, "locale": "pt-BR"})


def fig_faltas_por_dia(dia: pd.DataFrame) -> go.Figure | None:
    """Faltas por dia (sem justificativa e justificadas, empilhadas)."""
    if dia.empty or (dia[config.GRUPO_FALTA].sum() + dia[config.GRUPO_JUSTIFICADO].sum()) == 0:
        return None
    x = [d.strftime("%d/%m") for d in dia["data"]]
    fig = go.Figure()
    for grupo, nome in ((config.GRUPO_FALTA, "Sem justificativa"), (config.GRUPO_JUSTIFICADO, "Justificada")):
        fig.add_bar(x=x, y=dia[grupo], name=nome, marker=dict(color=config.COR_GRUPO[grupo],
                                                               line=dict(color="#FFFFFF", width=1)),
                    hovertemplate="%{x}<br>" + nome + ": <b>%{y}</b><extra></extra>")
    fig.update_layout(barmode="stack")
    fig.update_yaxes(title=None, rangemode="tozero", dtick=1 if dia[[config.GRUPO_FALTA,
                                                                     config.GRUPO_JUSTIFICADO]].sum(axis=1).max() <= 8
                     else None)
    fig.update_xaxes(type="category")
    return _layout_base(fig, 300)


def fig_ranking_faltas(ps: pd.DataFrame, top: int = 10) -> go.Figure | None:
    """Quem mais faltou: barras horizontais (sem justificativa + justificadas)."""
    if ps.empty or (ps["faltas"].sum() + ps["justificadas"].sum()) == 0:
        return None
    d = ps.assign(total=ps["faltas"] + ps["justificadas"])
    d = d[d["total"] > 0].sort_values(["faltas", "total"], ascending=False).head(top).iloc[::-1]
    nomes = [n if len(n) <= 26 else n[:25] + "…" for n in d["nome_servidor"]]
    fig = go.Figure()
    fig.add_bar(y=nomes, x=d["faltas"], orientation="h", name="Sem justificativa",
                marker=dict(color=config.COR_FALTA, line=dict(color="#FFFFFF", width=1)),
                hovertemplate="%{y}<br>Sem justificativa: <b>%{x}</b><extra></extra>")
    fig.add_bar(y=nomes, x=d["justificadas"], orientation="h", name="Justificada",
                marker=dict(color=config.COR_JUSTIFICADO, line=dict(color="#FFFFFF", width=1)),
                hovertemplate="%{y}<br>Justificadas: <b>%{x}</b><extra></extra>")
    fig.update_layout(barmode="stack")
    fig.update_xaxes(rangemode="tozero", gridcolor="#EEF1F5", showgrid=True,
                     dtick=1 if (d["faltas"] + d["justificadas"]).max() <= 8 else None)
    fig.update_yaxes(showgrid=False)
    return _layout_base(fig, max(240, 30 * len(d) + 70))


def fig_presenca_mes(pm: pd.DataFrame) -> go.Figure | None:
    """% de presença mês a mês (linha)."""
    if len(pm) < 2:
        return None
    fig = go.Figure()
    fig.add_scatter(x=pm["rotulo"], y=pm["pct_presenca"], mode="lines+markers+text", name="% presença",
                    line=dict(color=config.COR_PRIMARIA, width=2), marker=dict(size=8),
                    text=[ind.fmt_pct(v) for v in pm["pct_presenca"]], textposition="top center",
                    textfont=dict(size=11, color="#6B7280"),
                    hovertemplate="%{x}<br>Presença: <b>%{text}</b><extra></extra>")
    fig.update_yaxes(range=[max(0, pm["pct_presenca"].min() - 10), 103], ticksuffix="%")
    fig.update_xaxes(type="category")
    fig.update_layout(showlegend=False)
    return _layout_base(fig, 280)


def fig_grupos(g: pd.DataFrame, rotulo: str) -> go.Figure | None:
    """% de presença por grupo (barra horizontal, uma cor; começa no zero)."""
    if g.empty:
        return None
    d = g.iloc[::-1]
    fig = go.Figure()
    fig.add_bar(y=d["grupo_valor"], x=d["pct_presenca"], orientation="h", name="% presença",
                marker=dict(color=config.COR_PRIMARIA), text=[ind.fmt_pct(v) for v in d["pct_presenca"]],
                textposition="outside", cliponaxis=False,
                customdata=d[["servidores", "faltas", "justificadas"]].values,
                hovertemplate=("%{y}<br>Presença: <b>%{text}</b><br>Servidores: %{customdata[0]}"
                               "<br>Faltas sem justif.: %{customdata[1]}<br>Justificadas: %{customdata[2]}"
                               "<extra></extra>"))
    fig.update_xaxes(range=[0, 108], ticksuffix="%", showgrid=True, gridcolor="#EEF1F5")
    fig.update_layout(showlegend=False, margin=dict(l=8, r=60, t=8, b=8))
    return _layout_base(fig, max(220, 34 * len(d) + 60))


# ---------------------------------------------------------------------------
# Calendário individual
# ---------------------------------------------------------------------------

def calendario(dados: pd.DataFrame, periodo) -> html.Div:
    import calendar as cal

    marc = {d: s for d, s in zip(dados["data"], dados["status"])} if not dados.empty else {}
    celulas = [html.Div(d, className="cab") for d in config.DIAS_SEMANA_CURTO]
    for semana in cal.Calendar(0).monthdatescalendar(periodo.ano, periodo.mes):
        for d in semana:
            if d.month != periodo.mes:
                celulas.append(html.Div(className="cal-dia vazio"))
                continue
            status = marc.get(d)
            grupo = ind.grupo_do_status(status) if status else None
            classe = {config.GRUPO_PRESENTE: "P", config.GRUPO_FALTA: "F", config.GRUPO_JUSTIFICADO: "J"}.get(grupo, "")
            if not status and d.weekday() >= 5:
                classe = "fds"
            celulas.append(html.Div([html.Div(d.day, className="num"),
                                     html.Div(status.capitalize() if status else "", className="st")],
                                    className=f"cal-dia {classe}", title=status or "sem registro"))
    legenda = html.Div([
        html.Span([html.I(style={"background": "#E3F1E4"}), "Compareceu"]),
        html.Span([html.I(style={"background": "#F9E0E0"}), "Faltou"]),
        html.Span([html.I(style={"background": "#FDEFD9"}), "Atestado / declaração"]),
        html.Span([html.I(style={"background": "#FFFFFF", "border": "1px solid #E3E8EF"}), "Sem registro"]),
    ], className="legenda")
    return html.Div([html.Div(celulas, className="calendario"), legenda])
