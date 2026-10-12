"""Por servidor: a frequência de uma pessoa, dia a dia."""

from __future__ import annotations

from dash import Input, Output, State, callback, ctx, dcc, html

from src.model import crud
from src.services import exportar_excel as xls
from src.services import exportar_pdf as pdf
from src.services import indicadores as ind
from src.services import relatorios as rel
from src.ui import auth
from src.ui import componentes as c

P = "ind"


def layout(servidor: str | None = None):
    opcoes = c.opcoes_servidores()
    valor = int(servidor) if servidor and servidor.isdigit() else (opcoes[0]["value"] if opcoes else None)
    return html.Div([
        *c.cabecalho("Por servidor", "Escolha uma pessoa para ver os dias de presença, as faltas e o histórico."),
        html.Div([
            html.Div([html.Label("Servidor"),
                      dcc.Dropdown(id=f"{P}-servidor", options=opcoes, value=valor, clearable=False,
                                   placeholder="Digite o nome...")], className="filtro largo"),
            c.filtro_periodo(f"{P}-periodo"),
        ], className="filtros"),
        html.Div([
            c.botao("Baixar PDF (folha individual)", f"{P}-pdf", "exportar"),
            c.botao("Baixar Excel", f"{P}-xlsx", "exportar"),
            dcc.Download(id=f"{P}-download"),
        ], className="botoes", style={"marginBottom": "14px"}),
        dcc.Loading(html.Div(id=f"{P}-conteudo"), type="dot"),
    ])


def _dados(servidor_id, periodo_valor):
    periodo = ind.periodo_de_valor(periodo_valor)
    return rel.individual(periodo, int(servidor_id)), crud.list_servidores().set_index("id").loc[int(servidor_id)]


@callback(Output(f"{P}-conteudo", "children"), Input(f"{P}-servidor", "value"), Input(f"{P}-periodo", "value"))
def atualizar(servidor_id, periodo_valor):
    auth.exigir()
    if not servidor_id:
        return c.msg("Nenhum servidor cadastrado ainda.", "info")
    pac, srv = _dados(servidor_id, periodo_valor)
    r = pac.resumo
    linha = pac.servidores.iloc[0] if not pac.servidores.empty else None
    situacao = linha["situacao"] if linha is not None else "Sem registros"
    v = {k: c.valor(x) for k, x in srv.items()}
    dados_srv = " · ".join(str(x) for x in [
        f"Matrícula {v['matricula']}" if v["matricula"] else None, v["cargo_funcao"],
        f"Segmento {v['tipo_professor']}" if v["tipo_professor"] else None,
        f"Vínculo {v['tipo_vinculo']}" if v["tipo_vinculo"] else None, v["carga_horaria"],
        None if srv["ativo"] else "DESLIGADO",
    ] if x)

    if not r["registros"]:
        frase = f"Nenhum registro de {srv['nome_servidor']} em {pac.periodo.rotulo}."
    else:
        frase = (f"Em {pac.periodo.rotulo}, {srv['nome_servidor']} teve {ind.fmt_pct(r['pct_presenca'])} de presença: "
                 f"{r['presencas']} presenças, {r['faltas']} faltas sem justificativa e "
                 f"{r['justificadas']} justificadas, em {r['registros']} dias registrados.")
        if situacao == "Atenção":
            frase += f" Situação: ATENÇÃO ({linha['motivo']})."

    cor_sit = "#C62828" if situacao == "Atenção" else "#2E7D32"
    cards = html.Div([
        c.kpi("% de presença", ind.fmt_pct(r["pct_presenca"]), f"{r['registros']} dias registrados"),
        c.kpi("Presenças", r["presencas"], "compareceu", "#2E7D32"),
        c.kpi("Faltas sem justificativa", r["faltas"], "", "#C62828"),
        c.kpi("Faltas justificadas", r["justificadas"], "atestados e declarações", "#E68A00"),
        c.kpi("Situação", situacao, linha["motivo"] if linha is not None and linha["motivo"] else "", cor_sit),
    ], className="kpis")

    if pac.periodo.mensal:
        detalhe = c.bloco("Calendário do mês", c.calendario(pac.dados, pac.periodo),
                          sub="Cada quadrado é um dia. Passe o mouse para ver o status.")
    else:
        pm = ind.por_mes(pac.dados)
        detalhe = c.bloco("Mês a mês", c.grafico(c.fig_presenca_mes(pm), "Só há registros em um mês."),
                          c.tabela(f"{P}-meses", c.df_para_tela(pm), {
                              "rotulo": "Mês", "registros": "Dias registrados", "presencas": "Presenças",
                              "faltas": "Faltas sem justif.", "justificadas": "Faltas justif.",
                              "pct_presenca": "% presença"}, 12))

    oc = c.df_para_tela(ind.ocorrencias(pac.dados))
    ocorr = c.bloco("Ocorrências", c.tabela(f"{P}-ocorr", oc, {"data": "Data", "status": "Status",
                                                               "observacao": "Observação"}, 10)
                    if not oc.empty else c.msg("Nenhuma falta, atestado ou declaração no período.", "ok"),
                    sub="Faltas, atestados e declarações, do mais recente ao mais antigo.")
    return [
        html.P([html.B(srv["nome_servidor"]), " — ", dados_srv], style={"margin": "0 0 10px"}),
        cards, c.resumo_frases([frase]), html.Div([detalhe, ocorr], className="grade-2"),
    ]


@callback(
    Output(f"{P}-download", "data"),
    Input(f"{P}-pdf", "n_clicks"), Input(f"{P}-xlsx", "n_clicks"),
    State(f"{P}-servidor", "value"), State(f"{P}-periodo", "value"),
    prevent_initial_call=True,
)
def baixar(_a, _b, servidor_id, periodo_valor):
    auth.exigir()
    if not servidor_id:
        return None
    pac, srv = _dados(servidor_id, periodo_valor)
    nome = ind.chave_nome(srv["nome_servidor"]).replace(" ", "_")[:40]
    if ctx.triggered_id == f"{P}-pdf":
        dados = {**{k: c.valor(x) for k, x in srv.items()}, "id": int(servidor_id)}
        return dcc.send_bytes(pdf.pdf_individual([(pac, dados)]),
                              xls.nome_arquivo(f"frequencia_{nome}", pac.periodo, "pdf"))
    return dcc.send_bytes(xls.excel_visao(pac, ind.por_mes(pac.dados)),
                          xls.nome_arquivo(f"frequencia_{nome}", pac.periodo, "xlsx"))
