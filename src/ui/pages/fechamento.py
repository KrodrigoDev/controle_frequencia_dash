"""Fechamento do mês: confere pendências e exporta os relatórios (Excel e PDF)."""

from __future__ import annotations

import config
from dash import Input, Output, State, callback, ctx, dcc, html

from src.model import crud
from src.services import exportar_excel as xls
from src.services import exportar_pdf as pdf
from src.services import indicadores as ind
from src.services import relatorios as rel
from src.ui import auth
from src.ui import componentes as c

P = "fch"


def layout():
    return html.Div([
        *c.cabecalho("Fechamento do mês",
                     "Confira se a chamada está completa e baixe os relatórios do mês: planilha completa, "
                     "relatório geral para assinatura e folhas individuais."),
        html.Div([c.filtro_periodo(f"{P}-mes", apenas_meses=True, rotulo="Mês")], className="filtros"),
        dcc.Loading(html.Div(id=f"{P}-conteudo"), type="dot"),
        dcc.Download(id=f"{P}-download"),
    ])


def _checklist(pac) -> html.Div:
    r, pend = pac.resumo, pac.pendencias
    n_atencao = int((pac.servidores["situacao"] == "Atenção").sum())
    itens = [
        ("ok" if r["dias_com_chamada"] else "alerta",
         f"{ind.plural(r['dias_com_chamada'], 'dia')} com chamada lançada no mês."
         if r["dias_com_chamada"] else "Nenhuma chamada lançada neste mês."),
        ("ok" if pend.empty else "alerta",
         "Sem pendências: todos os servidores ativos têm registro nos dias com chamada." if pend.empty else
         f"{ind.plural(len(pend), 'lançamento pendente', 'lançamentos pendentes')} "
         f"em {ind.plural(pend['data'].nunique(), 'dia')}. Veja a aba “Pendências” e lance em “Fazer chamada”."),
        ("ok" if not n_atencao else "alerta",
         "Nenhum servidor em atenção." if not n_atencao else
         f"{ind.plural(n_atencao, 'servidor', 'servidores')} com {config.LIMITE_ALERTA_FALTAS} ou mais faltas sem justificativa."),
    ]
    return html.Div([
        html.Div([html.Div("✓" if t == "ok" else "!", className="icone"), html.Div(texto)], className=f"check {t}")
        for t, texto in itens
    ])


def _estilo_espelho(colunas_dia):
    cores = {"P": "#E3F1E4", "F": "#F9E0E0", "A": "#FDEFD9", "D": "#FDEFD9"}
    estilo = []
    for col in colunas_dia:
        for letra, cor in cores.items():
            estilo.append({"if": {"filter_query": f'{{{col}}} = "{letra}"', "column_id": col}, "backgroundColor": cor})
    return estilo


@callback(Output(f"{P}-conteudo", "children"), Input(f"{P}-mes", "value"))
def atualizar(mes_valor):
    auth.exigir()
    pac = rel.fechamento(ind.periodo_de_valor(mes_valor))
    esp = pac.espelho
    dias = [col for col in esp.columns if col.isdigit()] if esp is not None else []
    cols_esp = {"nome_servidor": "Servidor", **{d: d for d in dias}, "P": "P", "F": "F", "J": "J",
                "% presença": "%"}
    esp_tela = esp.assign(**{"% presença": esp["% presença"].map(ind.fmt_pct)}) if esp is not None else None
    opcoes_srv = [o for o in c.opcoes_servidores() if o["value"] in set(pac.servidores["id_servidor"])]

    tabela_esp = c.tabela(
        f"{P}-espelho", esp_tela, cols_esp, 50,
        style_data_conditional=_estilo_espelho(dias), sort_action="none",
        style_cell_conditional=[{"if": {"column_id": d}, "textAlign": "center", "minWidth": "28px",
                                 "width": "28px", "maxWidth": "34px", "padding": "4px 2px"} for d in [*dias, "P", "F", "J"]]
        + [{"if": {"column_id": "nome_servidor"}, "minWidth": "200px"}],
    ) if esp is not None and not esp.empty else c.msg("Sem servidores para o mês.", "info")

    pend = c.df_para_tela(pac.pendencias) if not pac.pendencias.empty else None
    oc = c.df_para_tela(ind.ocorrencias(pac.dados))

    exportar = c.bloco("Baixar relatórios", html.Div([
        c.botao("Excel completo do mês", f"{P}-xlsx", "primario"),
        c.botao("PDF geral (para assinatura)", f"{P}-pdf", "exportar"),
        c.botao("PDF individual — todos os servidores", f"{P}-pdf-todos", "exportar"),
    ], className="botoes"), html.Div([
        html.Div([html.Label("PDF individual de um servidor"),
                  dcc.Dropdown(id=f"{P}-servidor", options=opcoes_srv, placeholder="Escolha o servidor...")],
                 className="filtro largo"),
        c.botao("Baixar PDF do servidor", f"{P}-pdf-um", "exportar"),
    ], className="filtros", style={"marginTop": "12px", "marginBottom": 0}),
        sub="O Excel traz abas de resumo, por servidor, quadro do mês, por cargo/segmento, ocorrências, "
            "pendências e todos os lançamentos.")

    return [
        c.kpis_resumo(pac.resumo, int((pac.servidores["situacao"] == "Atenção").sum()), len(pac.pendencias)),
        html.Div([c.bloco("Antes de fechar", _checklist(pac)), c.bloco("Resumo do mês", c.resumo_frases(pac.frases))],
                 className="grade-2"),
        exportar,
        c.bloco(None, dcc.Tabs(className="abas", children=[
            dcc.Tab(label="Por servidor", children=[html.Br(), c.tabela_servidores(f"{P}-servidores",
                                                                                    pac.servidores, 25)]),
            dcc.Tab(label="Quadro do mês", children=[
                html.P("P = compareceu · F = faltou · A = atestado · D = declaração · em branco = sem registro.",
                       className="sub", style={"marginTop": "10px"}), tabela_esp]),
            dcc.Tab(label=f"Pendências ({len(pac.pendencias)})", children=[html.Br(), c.tabela(
                f"{P}-pend", pend, {"data": "Data", "nome_servidor": "Servidor", "cargo_funcao": "Cargo / função",
                                    "tipo_professor": "Segmento"}, 20) if pend is not None
                else c.msg("Nenhuma pendência. A chamada do mês está completa.", "ok")]),
            dcc.Tab(label=f"Ocorrências ({len(oc)})", children=[html.Br(), c.tabela(
                f"{P}-oc", oc, {"data": "Data", "nome_servidor": "Servidor", "cargo_funcao": "Cargo / função",
                                "status": "Status", "observacao": "Observação"}, 20, filter_action="native")
                if not oc.empty else c.msg("Nenhuma falta, atestado ou declaração no mês.", "ok")]),
        ])),
    ]


c.ligar_tabela_ao_individual(f"{P}-servidores")


@callback(
    Output(f"{P}-download", "data"),
    Input(f"{P}-xlsx", "n_clicks"), Input(f"{P}-pdf", "n_clicks"),
    Input(f"{P}-pdf-todos", "n_clicks"), Input(f"{P}-pdf-um", "n_clicks"),
    State(f"{P}-mes", "value"), State(f"{P}-servidor", "value"),
    prevent_initial_call=True,
)
def baixar(n1, n2, n3, n4, mes_valor, servidor_id):
    auth.exigir()
    if not any([n1, n2, n3, n4]):  # botões recém-criados disparam com n_clicks=0
        return None
    periodo = ind.periodo_de_valor(mes_valor)
    gatilho = ctx.triggered_id
    if gatilho == f"{P}-xlsx":
        return dcc.send_bytes(xls.excel_fechamento(rel.fechamento(periodo)),
                              xls.nome_arquivo("fechamento_frequencia", periodo, "xlsx"))
    if gatilho == f"{P}-pdf":
        return dcc.send_bytes(pdf.pdf_fechamento(rel.fechamento(periodo)),
                              xls.nome_arquivo("fechamento_frequencia", periodo, "pdf"))
    servidores = crud.list_servidores().set_index("id")
    if gatilho == f"{P}-pdf-um":
        if not servidor_id:
            return None
        ids = [int(servidor_id)]
    else:
        ids = list(rel.fechamento(periodo).servidores["id_servidor"])
        ids.sort(key=lambda i: ind.chave_nome(servidores.loc[i, "nome_servidor"]))
    pacotes = [(rel.individual(periodo, i), {**{k: c.valor(x) for k, x in servidores.loc[i].items()}, "id": i})
               for i in ids]
    sufixo = "todos" if len(ids) > 1 else ind.chave_nome(servidores.loc[ids[0], "nome_servidor"]).replace(" ", "_")
    return dcc.send_bytes(pdf.pdf_individual(pacotes), xls.nome_arquivo(f"folhas_individuais_{sufixo}", periodo, "pdf"))
