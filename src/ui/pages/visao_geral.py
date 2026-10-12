"""Visão geral: como está a frequência de todo mundo no período escolhido."""

from __future__ import annotations

from dash import ALL, Input, Output, State, callback, dcc, html

from src.services import exportar_excel as xls
from src.services import exportar_pdf as pdf
from src.services import indicadores as ind
from src.services import relatorios as rel
from src.ui import auth
from src.ui import componentes as c

P = "vg"


def layout():
    return html.Div([
        *c.cabecalho("Visão geral",
                     "Como está a frequência de todos no período. Use os filtros para olhar só um grupo; "
                     "deixe em branco para ver todos."),
        html.Div([c.filtro_periodo(f"{P}-periodo"), *c.filtros_dimensoes(P)], className="filtros"),
        html.Div([
            c.botao("Baixar Excel", f"{P}-xlsx", "exportar"),
            c.botao("Baixar PDF", f"{P}-pdf", "exportar"),
            dcc.Download(id=f"{P}-download"),
        ], className="botoes", style={"marginBottom": "14px"}),
        dcc.Loading(html.Div(id=f"{P}-conteudo"), type="dot"),
    ])


def _pacote(periodo_valor, ids, valores):
    periodo = ind.periodo_de_valor(periodo_valor)
    filtros = c.filtros_de_valores(ids, valores)
    return rel.montar(periodo, filtros, titulo="Visão geral da frequência", com_espelho=periodo.mensal,
                      dimensoes=["Cargo / função"])


@callback(
    Output(f"{P}-conteudo", "children"),
    Input(f"{P}-periodo", "value"),
    Input({"tipo": f"{P}-dim", "col": ALL}, "value"),
    State({"tipo": f"{P}-dim", "col": ALL}, "id"),
)
def atualizar(periodo_valor, valores, ids):
    auth.exigir()
    pac = _pacote(periodo_valor, ids, valores)
    if pac.dados.empty:
        return [c.resumo_frases(pac.frases),
                c.msg("Para começar, faça a chamada no menu “Fazer chamada”.", "info")]
    ps = pac.servidores
    n_atencao = int((ps["situacao"] == "Atenção").sum())
    pm = ind.por_mes(pac.dados)
    graficos = [
        html.Div([
            c.bloco("Faltas por dia", c.grafico(c.fig_faltas_por_dia(ind.por_dia(pac.dados)),
                                                "Nenhuma falta no período."),
                    sub="Quantas faltas houve em cada dia com chamada."),
            c.bloco("Quem mais faltou", c.grafico(c.fig_ranking_faltas(ps), "Nenhuma falta no período."),
                    sub="Os 10 servidores com mais faltas sem justificativa."),
        ], className="grade-2"),
    ]
    if len(pm) >= 2:
        graficos.append(c.bloco("Presença mês a mês", c.grafico(c.fig_presenca_mes(pm)),
                                sub="Percentual de presença em cada mês do período."))
    return [
        c.kpis_resumo(pac.resumo, n_atencao, len(pac.pendencias)),
        c.resumo_frases(pac.frases),
        *graficos,
        c.bloco("Frequência por servidor", c.tabela_servidores(f"{P}-tabela", ps),
                sub="Clique numa pessoa para ver o detalhe dela. Clique no título de uma coluna para ordenar; "
                    "digite na linha abaixo do título para buscar."),
    ]


c.ligar_tabela_ao_individual(f"{P}-tabela")


@callback(
    Output(f"{P}-download", "data"),
    Input(f"{P}-xlsx", "n_clicks"),
    Input(f"{P}-pdf", "n_clicks"),
    State(f"{P}-periodo", "value"),
    State({"tipo": f"{P}-dim", "col": ALL}, "value"),
    State({"tipo": f"{P}-dim", "col": ALL}, "id"),
    prevent_initial_call=True,
)
def baixar(n_xlsx, n_pdf, periodo_valor, valores, ids):
    from dash import ctx

    auth.exigir()
    pac = _pacote(periodo_valor, ids, valores)
    if ctx.triggered_id == f"{P}-pdf":
        return dcc.send_bytes(pdf.pdf_fechamento(pac), xls.nome_arquivo("frequencia", pac.periodo, "pdf"))
    return dcc.send_bytes(xls.excel_visao(pac, ind.por_mes(pac.dados)),
                          xls.nome_arquivo("frequencia", pac.periodo, "xlsx"))
