"""Relatórios em PDF (reportlab): fechamento mensal geral e folha individual.

Todas as funções devolvem `bytes`, prontos para o dcc.Download.
"""

from __future__ import annotations

import calendar
import datetime as dt
import io
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

import config
from src.services import indicadores as ind
from src.services.relatorios import Pacote

LOGO = Path(__file__).resolve().parents[2] / "assets" / "logo.png"

AZUL = colors.HexColor(config.COR_PRIMARIA)
CINZA = colors.HexColor("#6B7280")
LINHA = colors.HexColor("#D6DCE5")
ZEBRA = colors.HexColor("#F4F6FA")
FUNDO = {"P": "#E3F1E4", "F": "#F9E0E0", "A": "#FDEFD9", "D": "#FDEFD9"}

_base = getSampleStyleSheet()
EST = {
    "titulo": ParagraphStyle("t", parent=_base["Title"], fontSize=15, textColor=AZUL, spaceAfter=2, alignment=0),
    "sub": ParagraphStyle("s", parent=_base["Normal"], fontSize=9, textColor=CINZA),
    "h2": ParagraphStyle("h2", parent=_base["Heading2"], fontSize=11.5, textColor=AZUL, spaceBefore=8, spaceAfter=4),
    "txt": ParagraphStyle("p", parent=_base["Normal"], fontSize=9.5, leading=13),
    "cel": ParagraphStyle("c", parent=_base["Normal"], fontSize=7.5, leading=9),
    "kpi_v": ParagraphStyle("kv", parent=_base["Normal"], fontSize=16, leading=19, alignment=TA_CENTER,
                            fontName="Helvetica-Bold"),
    "kpi_l": ParagraphStyle("kl", parent=_base["Normal"], fontSize=7.5, leading=9, alignment=TA_CENTER,
                            textColor=CINZA),
}


def _esc(t) -> str:
    return (str(t) if t is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _rodape(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(CINZA)
    w, _ = doc.pagesize
    canvas.drawString(doc.leftMargin, 8 * mm,
                      f"{config.NOME_SISTEMA} · gerado em {dt.datetime.now().strftime('%d/%m/%Y %H:%M')}")
    canvas.drawRightString(w - doc.rightMargin, 8 * mm, f"Página {doc.page}")
    canvas.restoreState()


def _doc(buf, paisagem: bool, titulo: str) -> SimpleDocTemplate:
    return SimpleDocTemplate(buf, pagesize=landscape(A4) if paisagem else A4, title=titulo,
                             leftMargin=12 * mm, rightMargin=12 * mm, topMargin=11 * mm, bottomMargin=14 * mm)


def _cabecalho(titulo: str, subtitulo: str, largura: float) -> Table:
    texto = [Paragraph(_esc(f"{config.NOME_INSTITUICAO} — {titulo}"), EST["titulo"]),
             Paragraph(_esc(subtitulo), EST["sub"])]
    if LOGO.exists():
        logo = Image(str(LOGO), width=16 * mm, height=16 * mm, kind="proportional")
        t = Table([[logo, texto]], colWidths=[20 * mm, largura - 20 * mm])
    else:
        t = Table([[texto]], colWidths=[largura])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, 0), 1.2, AZUL),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    return t


def _kpis(itens: list[tuple[str, str]], largura: float) -> Table:
    linha_v = [Paragraph(_esc(v), EST["kpi_v"]) for _, v in itens]
    linha_l = [Paragraph(_esc(r), EST["kpi_l"]) for r, _ in itens]
    t = Table([linha_v, linha_l], colWidths=[largura / len(itens)] * len(itens))
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, LINHA), ("INNERGRID", (0, 0), (-1, -1), 0.6, colors.white),
        ("BACKGROUND", (0, 0), (-1, -1), ZEBRA), ("TOPPADDING", (0, 0), (-1, 0), 7),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 7),
    ]))
    return t


def _tabela(df: pd.DataFrame, cab: list[str], larguras: list[float], alinhar_dir: set[int] | None = None,
            destaque_col: int | None = None) -> Table:
    """Tabela zebrada; `destaque_col` = índice da coluna 'Situação' (pinta Atenção)."""
    dados = [[Paragraph(f"<b>{_esc(c)}</b>", ParagraphStyle("h", parent=EST["cel"], textColor=colors.white))
              for c in cab]]
    for row in df.itertuples(index=False):
        dados.append([Paragraph(_esc(v), EST["cel"]) for v in row])
    t = Table(dados, colWidths=larguras, repeatRows=1)
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), AZUL), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, LINHA), ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]
    for i in range(1, len(dados)):
        if i % 2 == 0:
            estilo.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
        if destaque_col is not None and df.iloc[i - 1, destaque_col] == "Atenção":
            estilo.append(("TEXTCOLOR", (destaque_col, i), (destaque_col, i), colors.HexColor(config.COR_FALTA)))
    for j in alinhar_dir or set():
        estilo.append(("ALIGN", (j, 1), (j, -1), "RIGHT"))
    t.setStyle(TableStyle(estilo))
    return t


def _tabela_servidores(ps: pd.DataFrame, largura: float) -> Table:
    df = ps.assign(pct=ps["pct_presenca"].map(ind.fmt_pct))[
        ["nome_servidor", "cargo_funcao", "registros", "presencas", "faltas", "justificadas", "pct", "situacao",
         "motivo"]].fillna("")
    cab = ["Servidor", "Cargo / função", "Dias reg.", "Presenças", "Faltas s/ just.", "Faltas just.", "% presença",
           "Situação", "Motivo"]
    prop = [0.21, 0.15, 0.07, 0.07, 0.08, 0.07, 0.08, 0.08, 0.19]
    return _tabela(df, cab, [p * largura for p in prop], {2, 3, 4, 5, 6}, destaque_col=7)


def _assinaturas(largura: float) -> Table:
    t = Table([["", "", ""], ["Responsável pelo lançamento", "", "Direção"]],
              colWidths=[largura * 0.4, largura * 0.2, largura * 0.4], rowHeights=[14 * mm, 6 * mm])
    t.setStyle(TableStyle([("LINEABOVE", (0, 1), (0, 1), 0.8, colors.black),
                           ("LINEABOVE", (2, 1), (2, 1), 0.8, colors.black),
                           ("ALIGN", (0, 1), (-1, 1), "CENTER"), ("FONTSIZE", (0, 1), (-1, 1), 8.5)]))
    return t


def _espelho(esp: pd.DataFrame, periodo, largura: float) -> Table:
    dias = [c for c in esp.columns if c.isdigit()]
    cab = ["Servidor", *dias, "P", "F", "J", "%"]
    nome_w = 52 * mm
    resto = largura - nome_w
    w_dia = resto / (len(dias) + 5.2)
    larguras = [nome_w, *[w_dia] * len(dias), w_dia * 1.0, w_dia * 1.0, w_dia * 1.0, w_dia * 2.2]
    pequeno = ParagraphStyle("e", parent=EST["cel"], fontSize=6.6, leading=7.6)
    dados = [cab]
    for _, r in esp.iterrows():
        linha = [Paragraph(_esc(r["nome_servidor"]), pequeno)]
        linha += [r[c] for c in dias]
        linha += [r[c] for c in ("P", "F", "J")]
        linha.append(ind.fmt_pct(r["% presença"]))
        dados.append(linha)
    t = Table(dados, colWidths=larguras, repeatRows=1)
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), AZUL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 6.6), ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("GRID", (0, 0), (-1, -1), 0.3, LINHA),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("LEFTPADDING", (1, 0), (-1, -1), 0), ("RIGHTPADDING", (1, 0), (-1, -1), 0),
    ]
    for j, dia in enumerate(dias, start=1):
        if dt.date(periodo.ano, periodo.mes, int(dia)).weekday() >= 5:
            estilo.append(("BACKGROUND", (j, 0), (j, 0), colors.HexColor("#8A94A6")))
        for i in range(1, len(dados)):
            v = dados[i][j]
            if v in FUNDO:
                estilo.append(("BACKGROUND", (j, i), (j, i), colors.HexColor(FUNDO[v])))
    t.setStyle(TableStyle(estilo))
    return t


def _legenda() -> Paragraph:
    return Paragraph(
        "<b>Legenda:</b> P = compareceu · F = faltou · A = atestado · D = declaração · em branco = sem registro. "
        "Colunas cinza = sábado/domingo. % presença = presenças ÷ dias registrados. "
        f"<b>Atenção</b> = {config.LIMITE_ALERTA_FALTAS} ou mais faltas sem justificativa no período.", EST["sub"])


# ---------------------------------------------------------------------------
# Relatórios
# ---------------------------------------------------------------------------

def pdf_fechamento(pacote: Pacote) -> bytes:
    """Fechamento mensal (paisagem): resumo, quem precisa de atenção, tabela
    por servidor, quadro do mês, comparativos por grupo, pendências e assinaturas."""
    buf = io.BytesIO()
    doc = _doc(buf, True, f"Fechamento {pacote.periodo.rotulo}")
    W = doc.width
    r = pacote.resumo
    s: list = [
        _cabecalho(pacote.titulo, f"Período: {pacote.periodo.rotulo} · {pacote.filtros_txt}", W),
        Spacer(1, 5 * mm),
        _kpis([("% de presença", ind.fmt_pct(r["pct_presenca"])), ("Servidores", str(r["servidores"])),
               ("Dias com chamada", str(r["dias_com_chamada"])), ("Faltas sem justificativa", str(r["faltas"])),
               ("Faltas justificadas", str(r["justificadas"])), ("Pendências", str(len(pacote.pendencias)))], W),
        Spacer(1, 4 * mm),
        Paragraph("Resumo", EST["h2"]),
    ]
    s += [Paragraph("• " + _esc(f), EST["txt"]) for f in pacote.frases]

    atencao = pacote.servidores[pacote.servidores["situacao"] == "Atenção"]
    if not atencao.empty:
        s += [Paragraph("Quem precisa de atenção", EST["h2"]),
              _tabela(atencao[["nome_servidor", "cargo_funcao", "faltas", "justificadas", "motivo"]].fillna(""),
                      ["Servidor", "Cargo / função", "Faltas s/ just.", "Faltas just.", "Motivo"],
                      [W * 0.28, W * 0.2, W * 0.1, W * 0.1, W * 0.32], {2, 3})]

    s += [Paragraph("Frequência por servidor", EST["h2"])]
    s += [_tabela_servidores(pacote.servidores, W) if not pacote.servidores.empty
          else Paragraph("Sem registros no período.", EST["txt"])]

    if pacote.espelho is not None and not pacote.espelho.empty:
        s += [PageBreak(), Paragraph(f"Quadro do mês — {pacote.periodo.rotulo}", EST["h2"]), _legenda(),
              Spacer(1, 2 * mm), _espelho(pacote.espelho, pacote.periodo, W)]

    for rotulo, g in pacote.grupos.items():
        if g.empty or (g["grupo_valor"] == "Não informado").all():
            continue
        df = g.assign(pct=g["pct_presenca"].map(ind.fmt_pct))[
            ["grupo_valor", "servidores", "registros", "presencas", "faltas", "justificadas", "pct",
             "servidores_atencao"]]
        s += [KeepTogether([
            Paragraph(f"Comparativo por {rotulo.lower()}", EST["h2"]),
            _tabela(df, [rotulo, "Servidores", "Dias reg.", "Presenças", "Faltas s/ just.", "Faltas just.",
                         "% presença", "Em atenção"],
                    [W * 0.28] + [W * 0.72 / 7] * 7, {1, 2, 3, 4, 5, 6, 7})])]

    if not pacote.pendencias.empty:
        pend = pacote.pendencias.assign(data=pacote.pendencias["data"].map(ind.fmt_data)).fillna("")
        s += [Paragraph("Lançamentos pendentes", EST["h2"]),
              Paragraph("Servidores ativos sem registro em dias em que houve chamada. Lance antes de fechar o mês.",
                        EST["sub"]),
              _tabela(pend, ["Data", "Servidor", "Cargo / função", "Segmento"],
                      [W * 0.12, W * 0.38, W * 0.28, W * 0.22])]

    s += [Spacer(1, 10 * mm), KeepTogether([_assinaturas(W)])]
    doc.build(s, onFirstPage=_rodape, onLaterPages=_rodape)
    return buf.getvalue()


def _calendario(dados: pd.DataFrame, periodo, largura: float) -> Table:
    """Calendário do mês com a letra do status em cada dia."""
    marc = {d: ind.sigla(st) for d, st in zip(dados["data"], dados["status"])} if not dados.empty else {}
    semanas = calendar.Calendar(firstweekday=0).monthdatescalendar(periodo.ano, periodo.mes)
    cab = config.DIAS_SEMANA_CURTO
    linhas = [cab]
    estilo = [("BACKGROUND", (0, 0), (-1, 0), AZUL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
              ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
              ("GRID", (0, 0), (-1, -1), 0.4, LINHA), ("FONTSIZE", (0, 0), (-1, -1), 8.5)]
    for i, semana in enumerate(semanas, start=1):
        linha = []
        for j, d in enumerate(semana):
            if d.month != periodo.mes:
                linha.append("")
                estilo.append(("BACKGROUND", (j, i), (j, i), ZEBRA))
                continue
            letra = marc.get(d, "")
            linha.append(f"{d.day}\n{letra}" if letra else f"{d.day}\n·")
            if letra in FUNDO:
                estilo.append(("BACKGROUND", (j, i), (j, i), colors.HexColor(FUNDO[letra])))
        linhas.append(linha)
    t = Table(linhas, colWidths=[largura / 7] * 7, rowHeights=[6 * mm] + [11 * mm] * len(semanas))
    t.setStyle(TableStyle(estilo))
    return t


def _folha_individual(pacote: Pacote, servidor: dict, W: float) -> list:
    r = pacote.resumo
    linha_srv = pacote.servidores.iloc[0] if not pacote.servidores.empty else None
    situacao = linha_srv["situacao"] if linha_srv is not None else "Sem registros"
    motivo = linha_srv["motivo"] if linha_srv is not None else ""
    dados_srv = (f"<b>{_esc(servidor.get('nome_servidor'))}</b> · Matrícula: {_esc(servidor.get('matricula') or '—')}"
                 f" · {_esc(servidor.get('cargo_funcao') or '—')}"
                 + (f" · Segmento: {_esc(servidor.get('tipo_professor'))}" if servidor.get("tipo_professor") else ""))
    s: list = [
        _cabecalho("Frequência individual", f"Período: {pacote.periodo.rotulo}", W),
        Spacer(1, 4 * mm), Paragraph(dados_srv, EST["txt"]), Spacer(1, 3 * mm),
        _kpis([("% de presença", ind.fmt_pct(r["pct_presenca"])), ("Dias registrados", str(r["registros"])),
               ("Presenças", str(r["presencas"])), ("Faltas sem justificativa", str(r["faltas"])),
               ("Faltas justificadas", str(r["justificadas"]))], W),
        Spacer(1, 3 * mm),
        Paragraph(f"<b>Situação:</b> {_esc(situacao)}" + (f" — {_esc(motivo)}" if motivo else ""), EST["txt"]),
    ]
    if pacote.periodo.mensal:
        s += [Paragraph("Calendário do mês", EST["h2"]), _calendario(pacote.dados, pacote.periodo, W),
              Spacer(1, 1.5 * mm),
              Paragraph("P = compareceu · F = faltou · A = atestado · D = declaração · “·” = sem registro",
                        EST["sub"])]
    else:
        pm = ind.por_mes(pacote.dados)
        if not pm.empty:
            s += [Paragraph("Mês a mês", EST["h2"]),
                  _tabela(pm.assign(pct=pm["pct_presenca"].map(ind.fmt_pct))[
                      ["rotulo", "registros", "presencas", "faltas", "justificadas", "pct"]],
                      ["Mês", "Dias reg.", "Presenças", "Faltas s/ just.", "Faltas just.", "% presença"],
                      [W * 0.2] + [W * 0.16] * 5, {1, 2, 3, 4, 5})]
    oc = ind.ocorrencias(pacote.dados)
    s += [Paragraph("Ocorrências (faltas, atestados e declarações)", EST["h2"])]
    if oc.empty:
        s += [Paragraph("Nenhuma ocorrência no período.", EST["txt"])]
    else:
        oc = oc.assign(data=oc["data"].map(ind.fmt_data))[["data", "status", "observacao"]].fillna("")
        s += [_tabela(oc, ["Data", "Status", "Observação"], [W * 0.15, W * 0.2, W * 0.65])]
    s += [Spacer(1, 12 * mm), KeepTogether([_assinaturas(W)])]
    return s


def pdf_individual(pacotes: list[tuple[Pacote, dict]]) -> bytes:
    """Uma folha (retrato) por servidor. `pacotes` = [(pacote_individual, dados_do_servidor), ...]."""
    buf = io.BytesIO()
    doc = _doc(buf, False, "Frequência individual")
    s: list = []
    for i, (pacote, servidor) in enumerate(pacotes):
        if i:
            s.append(PageBreak())
        s += _folha_individual(pacote, servidor, doc.width)
    if not s:
        s = [Paragraph("Nenhum servidor selecionado.", EST["txt"])]
    doc.build(s, onFirstPage=_rodape, onLaterPages=_rodape)
    return buf.getvalue()
