"""Exportação para Excel (.xlsx) com abas formatadas (openpyxl).

Todas as funções devolvem `bytes`, prontos para o dcc.Download.
"""

from __future__ import annotations

import datetime as dt
import io

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

import config
from src.services import indicadores as ind
from src.services.relatorios import Pacote

AZUL = config.COR_PRIMARIA.lstrip("#")
FUNDO_SIGLA = {"P": "E3F1E4", "F": "F9E0E0", "A": "FDEFD9", "D": "FDEFD9"}
FINO = Side(style="thin", color="D6DCE5")
BORDA = Border(left=FINO, right=FINO, top=FINO, bottom=FINO)

# Nome amigável das colunas nas planilhas
NOMES = {
    "nome_servidor": "Servidor", "matricula": "Matrícula", "cargo_funcao": "Cargo / função",
    "tipo_professor": "Segmento", "tipo_servidor": "Tipo de servidor", "tipo_vinculo": "Vínculo",
    "carga_horaria": "Carga horária", "registros": "Dias registrados", "presencas": "Presenças",
    "faltas": "Faltas sem justificativa", "justificadas": "Faltas justificadas", "outros": "Outros",
    "pct_presenca": "% presença", "situacao": "Situação", "motivo": "Motivo",
    "grupo_valor": "Grupo", "servidores": "Servidores", "servidores_atencao": "Servidores em atenção",
    "data": "Data", "status": "Status", "grupo": "Tipo", "observacao": "Observação", "rotulo": "Mês",
}


def _tabela(ws, df: pd.DataFrame, linha_ini: int = 1, larguras: dict | None = None) -> int:
    """Escreve df com cabeçalho azul, bordas e filtro. Devolve a próxima linha livre."""
    df = df.rename(columns=NOMES)
    for j, col in enumerate(df.columns, start=1):
        c = ws.cell(row=linha_ini, column=j, value=col)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=AZUL)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BORDA
    for i, row in enumerate(df.itertuples(index=False), start=linha_ini + 1):
        for j, valor in enumerate(row, start=1):
            if isinstance(valor, float) and pd.isna(valor):
                valor = None
            c = ws.cell(row=i, column=j, value=valor)
            c.border = BORDA
            col = df.columns[j - 1]
            if isinstance(valor, dt.date):
                c.number_format = "DD/MM/YYYY"
            if col in ("% presença",) and valor is not None:
                c.value = valor / 100
                c.number_format = "0.0%"
            if col == "Situação" and valor == "Atenção":
                c.font = Font(bold=True, color=config.COR_FALTA.lstrip("#"))
    ultima = linha_ini + len(df)
    if len(df.columns):
        ws.auto_filter.ref = f"A{linha_ini}:{get_column_letter(len(df.columns))}{max(ultima, linha_ini)}"
    for j, col in enumerate(df.columns, start=1):
        largura = (larguras or {}).get(col)
        if largura is None:
            maior = max([len(str(col))] + [len(str(v)) for v in df.iloc[:, j - 1].head(300)]) if len(df) else len(col)
            largura = min(max(10, maior + 2), 45)
        ws.column_dimensions[get_column_letter(j)].width = largura
    ws.freeze_panes = ws.cell(row=linha_ini + 1, column=1)
    return ultima + 2


def _cabecalho(ws, titulo: str, pacote: Pacote) -> int:
    ws["A1"] = f"{config.NOME_INSTITUICAO} — {titulo}"
    ws["A1"].font = Font(bold=True, size=14, color=AZUL)
    ws["A2"] = f"Período: {pacote.periodo.rotulo}   ·   {pacote.filtros_txt}"
    ws["A3"] = f"Gerado em {dt.datetime.now().strftime('%d/%m/%Y %H:%M')}"
    ws["A3"].font = Font(italic=True, color="6B7280")
    return 5


def _aba_resumo(wb: Workbook, pacote: Pacote, titulo: str) -> None:
    ws = wb.active
    ws.title = "Resumo"
    linha = _cabecalho(ws, titulo, pacote)
    ws.cell(row=linha, column=1, value="Resumo").font = Font(bold=True, size=12)
    for frase in pacote.frases:
        linha += 1
        ws.cell(row=linha, column=1, value="• " + frase)
    linha += 2
    r = pacote.resumo
    numeros = pd.DataFrame([
        ("Servidores no período", r["servidores"]),
        ("Dias com chamada", r["dias_com_chamada"]),
        ("Dias registrados (total)", r["registros"]),
        ("Presenças", r["presencas"]),
        ("Faltas sem justificativa", r["faltas"]),
        ("Faltas justificadas (atestado/declaração)", r["justificadas"]),
        ("Outros status", r["outros"]),
        ("% de presença", ind.fmt_pct(r["pct_presenca"])),
    ], columns=["Indicador", "Valor"])
    linha = _tabela(ws, numeros, linha, {"Indicador": 44, "Valor": 14})
    ws.freeze_panes = None
    ws.auto_filter.ref = None
    ws.cell(row=linha, column=1, value="Como ler").font = Font(bold=True)
    legenda = [
        "P = compareceu · F = faltou · A = atestado · D = declaração (no Quadro do mês).",
        "% presença = presenças ÷ dias registrados do servidor no período.",
        f"Atenção = {config.LIMITE_ALERTA_FALTAS} ou mais faltas sem justificativa no período "
        "(atestado e declaração não contam).",
        "Pendência = servidor ativo sem registro em um dia em que houve chamada.",
    ]
    for t in legenda:
        linha += 1
        ws.cell(row=linha, column=1, value=t)


def _aba_espelho(wb: Workbook, esp: pd.DataFrame, periodo) -> None:
    ws = wb.create_sheet("Quadro do mês")
    df = esp.drop(columns=["id_servidor"])
    larg = {"Servidor": 34, "Matrícula": 12, "Cargo / função": 22, "P": 5, "F": 5, "J": 5, "% presença": 11}
    larg.update({c: 4.2 for c in df.columns if c.isdigit()})
    _tabela(ws, df, 1, larg)
    # cor de fundo por letra + destaque dos fins de semana no cabeçalho
    cols = list(df.rename(columns=NOMES).columns)
    for j, col in enumerate(cols, start=1):
        if not col.isdigit():
            continue
        dia = dt.date(periodo.ano, periodo.mes, int(col))
        if dia.weekday() >= 5:
            ws.cell(row=1, column=j).fill = PatternFill("solid", fgColor="8A94A6")
        for i in range(2, len(df) + 2):
            c = ws.cell(row=i, column=j)
            c.alignment = Alignment(horizontal="center")
            if c.value in FUNDO_SIGLA:
                c.fill = PatternFill("solid", fgColor=FUNDO_SIGLA[c.value])
    ws.freeze_panes = "D2"


def _aba(wb: Workbook, nome: str, df: pd.DataFrame) -> None:
    ws = wb.create_sheet(nome[:31])
    if df.empty:
        ws["A1"] = "Sem registros para o período."
        return
    _tabela(ws, df)


def _bytes(wb: Workbook) -> bytes:
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _sem_ids(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop(columns=[c for c in df.columns if c.startswith("id_")], errors="ignore")


def _lancamentos(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    cols = ["data", "nome_servidor", "matricula", "cargo_funcao", "tipo_professor", "tipo_servidor",
            "tipo_vinculo", "status", "grupo", "observacao"]
    return df.sort_values(["data", "nome_servidor"])[cols]


def excel_fechamento(pacote: Pacote) -> bytes:
    """Fechamento mensal: Resumo, Por servidor, Quadro do mês, grupos,
    Ocorrências, Pendências e Lançamentos."""
    wb = Workbook()
    _aba_resumo(wb, pacote, "Fechamento mensal de frequência")
    _aba(wb, "Por servidor", _sem_ids(pacote.servidores))
    if pacote.espelho is not None:
        _aba_espelho(wb, pacote.espelho, pacote.periodo)
    nomes_aba = {"Cargo / função": "Por cargo", "Segmento (professores)": "Por segmento",
                 "Tipo de servidor": "Por tipo", "Vínculo": "Por vínculo", "Carga horária": "Por carga horária"}
    for rotulo, df in pacote.grupos.items():
        _aba(wb, nomes_aba.get(rotulo, rotulo), df)
    _aba(wb, "Ocorrências", ind.ocorrencias(pacote.dados))
    _aba(wb, "Pendências", pacote.pendencias)
    _aba(wb, "Lançamentos", _lancamentos(pacote.dados))
    return _bytes(wb)


def excel_visao(pacote: Pacote, por_mes: pd.DataFrame | None = None) -> bytes:
    """Visão geral filtrada: Resumo, Por servidor, Por mês, Ocorrências, Lançamentos."""
    wb = Workbook()
    _aba_resumo(wb, pacote, pacote.titulo)
    _aba(wb, "Por servidor", _sem_ids(pacote.servidores))
    for rotulo, df in pacote.grupos.items():
        _aba(wb, f"Por {rotulo.split(' ')[0].lower()}", df)
    if por_mes is not None and not por_mes.empty:
        _aba(wb, "Por mês", por_mes.drop(columns=["ano", "mes"]))
    _aba(wb, "Ocorrências", ind.ocorrencias(pacote.dados))
    _aba(wb, "Lançamentos", _lancamentos(pacote.dados))
    return _bytes(wb)


def excel_tabela(nome_aba: str, df: pd.DataFrame) -> bytes:
    """Uma tabela qualquer numa planilha (ex.: cadastro de servidores)."""
    wb = Workbook()
    ws = wb.active
    ws.title = nome_aba[:31]
    _tabela(ws, _sem_ids(df.drop(columns=["id"], errors="ignore")))
    return _bytes(wb)


def nome_arquivo(prefixo: str, periodo, ext: str) -> str:
    rot = periodo.rotulo.replace("/", "-").replace(" ", "_").lower()
    return f"{prefixo}_{rot}.{ext}"
