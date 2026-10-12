"""Por grupo: compara a frequência entre cargos, segmentos, vínculos..."""

from __future__ import annotations

import pandas as pd
from dash import Input, Output, State, callback, dcc, html

from src.services import exportar_excel as xls
from src.services import indicadores as ind
from src.services import relatorios as rel
from src.ui import auth
from src.ui import componentes as c

P = "grp"


def layout():
    return html.Div([
        *c.cabecalho("Por grupo",
                     "Compare a frequência entre grupos de servidores. Clique numa linha da tabela para ver "
                     "quem faz parte do grupo."),
        html.Div([
            c.filtro_periodo(f"{P}-periodo"),
            html.Div([html.Label("Comparar por"),
                      dcc.Dropdown(id=f"{P}-dim", options=list(ind.DIMENSOES), value="Cargo / função",
                                   clearable=False)], className="filtro"),
        ], className="filtros"),
        html.Div([c.botao("Baixar Excel", f"{P}-xlsx", "exportar"), dcc.Download(id=f"{P}-download")],
                 className="botoes", style={"marginBottom": "14px"}),
        dcc.Loading(html.Div(id=f"{P}-conteudo"), type="dot"),
        html.Div(id=f"{P}-membros"),
    ])


def _calcular(periodo_valor, dimensao):
    periodo = ind.periodo_de_valor(periodo_valor)
    pac = rel.montar(periodo, titulo=f"Frequência por {dimensao.lower()}", com_pendencias=False,
                     dimensoes=[dimensao])
    return pac, pac.grupos[dimensao]


COLS = {"grupo_valor": "Grupo", "servidores": "Servidores", "registros": "Dias registrados",
        "presencas": "Presenças", "faltas": "Faltas sem justif.", "justificadas": "Faltas justif.",
        "pct_presenca": "% presença", "servidores_atencao": "Servidores em atenção"}


@callback(Output(f"{P}-conteudo", "children"), Input(f"{P}-periodo", "value"), Input(f"{P}-dim", "value"))
def atualizar(periodo_valor, dimensao):
    auth.exigir()
    pac, g = _calcular(periodo_valor, dimensao)
    if g.empty:
        return c.msg(f"Nenhuma presença lançada em {pac.periodo.rotulo}.", "info")
    pior, melhor = g.iloc[0], g.iloc[-1]
    frases = [f"Comparando {len(g)} grupos por {dimensao.lower()} em {pac.periodo.rotulo}."]
    if len(g) > 1:
        frases.append(f"Menor presença: {pior['grupo_valor']} ({ind.fmt_pct(pior['pct_presenca'])}). "
                      f"Maior presença: {melhor['grupo_valor']} ({ind.fmt_pct(melhor['pct_presenca'])}).")
    com_atencao = g[g["servidores_atencao"] > 0]
    if not com_atencao.empty:
        frases.append("Grupos com servidores em atenção: " + ", ".join(
            f"{r.grupo_valor} ({r.servidores_atencao})" for r in com_atencao.itertuples()) + ".")
    return [
        c.resumo_frases(frases),
        html.Div([
            c.bloco("% de presença por grupo", c.grafico(c.fig_grupos(g, dimensao)),
                    sub="Do menor para o maior. Passe o mouse para ver os números."),
            c.bloco("Números por grupo", c.tabela(f"{P}-tabela", c.df_para_tela(g), COLS, 20,
                                                   row_selectable="single", selected_rows=[])),
        ], className="grade-2"),
    ]


@callback(
    Output(f"{P}-membros", "children"),
    Input(f"{P}-tabela", "selected_rows"),
    State(f"{P}-tabela", "data"), State(f"{P}-periodo", "value"), State(f"{P}-dim", "value"),
    prevent_initial_call=True,
)
def membros(selecionadas, dados, periodo_valor, dimensao):
    auth.exigir()
    if not selecionadas:
        return None
    grupo = dados[selecionadas[0]]["grupo_valor"]
    periodo = ind.periodo_de_valor(periodo_valor)
    pac = rel.montar(periodo, {ind.DIMENSOES[dimensao]: [grupo]}, com_pendencias=False)
    return c.bloco(f"Servidores do grupo: {grupo}", c.tabela_servidores(f"{P}-membros-tab", pac.servidores),
                   sub=pac.frases[0] if pac.frases else None)


c.ligar_tabela_ao_individual(f"{P}-membros-tab")


@callback(
    Output(f"{P}-download", "data"), Input(f"{P}-xlsx", "n_clicks"),
    State(f"{P}-periodo", "value"), State(f"{P}-dim", "value"), prevent_initial_call=True,
)
def baixar(_n, periodo_valor, dimensao):
    auth.exigir()
    pac, g = _calcular(periodo_valor, dimensao)
    # todas as dimensões numa planilha só: uma aba por forma de agrupar
    for rotulo in ind.DIMENSOES:
        pac.grupos[rotulo] = ind.por_grupo(pac.dados, ind.DIMENSOES[rotulo])
    return dcc.send_bytes(xls.excel_visao(pac, ind.por_mes(pac.dados) if not pac.dados.empty else pd.DataFrame()),
                          xls.nome_arquivo("frequencia_por_grupo", pac.periodo, "xlsx"))
