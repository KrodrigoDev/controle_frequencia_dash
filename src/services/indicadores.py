"""Cálculos de frequência (só pandas — não conhece tela nem banco).

Entrada: o DataFrame de `crud.presenca_detalhada()` (uma linha por presença).
Saída: tabelas e números prontos para tela, Excel e PDF. Como tudo passa por
aqui, a tela e os relatórios exportados SEMPRE mostram os mesmos valores.

Regras (ver config.py):
    * Presença  = status em STATUS_PRESENTE   (COMPARECEU)
    * Falta     = status em STATUS_FALTA      (FALTOU)
    * Falta justificada = STATUS_JUSTIFICADO  (ATESTADO, DECLARAÇÃO)
    * % de presença = presenças ÷ dias registrados do servidor
    * "Atenção" = faltas sem justificativa >= LIMITE_ALERTA_FALTAS no período
                  (atestado/declaração NÃO geram atenção)
"""

from __future__ import annotations

import calendar
import datetime as dt
import unicodedata
from dataclasses import dataclass

import pandas as pd

import config

# Dimensões pelas quais dá para comparar grupos de servidores: rótulo -> coluna
DIMENSOES = {
    "Cargo / função": "cargo_funcao",
    "Segmento (professores)": "tipo_professor",
    "Tipo de servidor": "tipo_servidor",
    "Vínculo": "tipo_vinculo",
    "Carga horária": "carga_horaria",
}

ORDEM_GRUPOS = [config.GRUPO_PRESENTE, config.GRUPO_JUSTIFICADO, config.GRUPO_FALTA, config.GRUPO_OUTROS]


# ---------------------------------------------------------------------------
# Período
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Periodo:
    inicio: dt.date
    fim: dt.date
    rotulo: str  # ex.: "Outubro/2026", "Ano de 2026"
    mensal: bool = False

    @property
    def ano(self) -> int:
        return self.inicio.year

    @property
    def mes(self) -> int:
        return self.inicio.month


def periodo_mes(ano: int, mes: int) -> Periodo:
    ultimo = calendar.monthrange(ano, mes)[1]
    return Periodo(dt.date(ano, mes, 1), dt.date(ano, mes, ultimo), f"{config.MESES_PT[mes]}/{ano}", True)


def periodo_ano(ano: int) -> Periodo:
    return Periodo(dt.date(ano, 1, 1), dt.date(ano, 12, 31), f"Ano de {ano}")


def periodo_de_valor(valor: str | None, hoje: dt.date | None = None) -> Periodo:
    """Converte o valor do seletor de período ('m:2026-10', 'a:2026', 'tudo')."""
    hoje = hoje or dt.date.today()
    if valor and valor.startswith("m:"):
        ano, mes = valor[2:].split("-")
        return periodo_mes(int(ano), int(mes))
    if valor and valor.startswith("a:"):
        return periodo_ano(int(valor[2:]))
    if valor == "tudo":
        return Periodo(dt.date(1900, 1, 1), dt.date(2999, 12, 31), "Todo o período")
    return periodo_mes(hoje.year, hoje.month)


def opcoes_periodo(primeira: dt.date | None, ultima: dt.date | None, hoje: dt.date | None = None,
                   incluir_anos: bool = True) -> list[dict]:
    """Opções do seletor: todos os meses com dados (do mais recente ao mais
    antigo) + o mês atual, depois os anos e 'Todo o período'."""
    hoje = hoje or dt.date.today()
    primeira = min(primeira or hoje, hoje)
    ultima = max(ultima or hoje, hoje)
    meses = []
    a, m = ultima.year, ultima.month
    while (a, m) >= (primeira.year, primeira.month):
        meses.append({"label": f"{config.MESES_PT[m]}/{a}", "value": f"m:{a}-{m:02d}"})
        a, m = (a, m - 1) if m > 1 else (a - 1, 12)
    if not incluir_anos:
        return meses
    anos = [{"label": f"Ano de {x}", "value": f"a:{x}"} for x in range(ultima.year, primeira.year - 1, -1)]
    return meses + anos + [{"label": "Todo o período", "value": "tudo"}]


# ---------------------------------------------------------------------------
# Preparação
# ---------------------------------------------------------------------------

def grupo_do_status(status: str | None) -> str:
    if status in config.STATUS_PRESENTE:
        return config.GRUPO_PRESENTE
    if status in config.STATUS_FALTA:
        return config.GRUPO_FALTA
    if status in config.STATUS_JUSTIFICADO:
        return config.GRUPO_JUSTIFICADO
    return config.GRUPO_OUTROS


def preparar(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza tipos e acrescenta a coluna `grupo`."""
    df = df.copy()
    if df.empty:
        df["grupo"] = pd.Series(dtype="object")
        return df
    df["data"] = pd.to_datetime(df["data"]).dt.date
    df["grupo"] = df["status"].map(grupo_do_status)
    for col in DIMENSOES.values():
        if col in df:
            df[col] = df[col].fillna("Não informado")
    return df


def filtrar(df: pd.DataFrame, periodo: Periodo | None = None, **filtros) -> pd.DataFrame:
    """Filtra pelo período e por listas de valores (lista vazia/None = todos).
    Ex.: filtrar(df, periodo, cargo_funcao=["VIGIA"], id_servidor=[3])"""
    if df.empty:
        return df
    if periodo is not None:
        df = df[(df["data"] >= periodo.inicio) & (df["data"] <= periodo.fim)]
    for coluna, valores in filtros.items():
        if valores:
            valores = valores if isinstance(valores, (list, tuple, set)) else [valores]
            df = df[df[coluna].isin(valores)]
    return df


# ---------------------------------------------------------------------------
# Números
# ---------------------------------------------------------------------------

def _pct(parte: float, total: float) -> float:
    return round(parte / total * 100, 1) if total else 0.0


def _contagens(df: pd.DataFrame) -> dict:
    g = df["grupo"].value_counts() if not df.empty else pd.Series(dtype=int)
    registros = int(len(df))
    presencas = int(g.get(config.GRUPO_PRESENTE, 0))
    faltas = int(g.get(config.GRUPO_FALTA, 0))
    justificadas = int(g.get(config.GRUPO_JUSTIFICADO, 0))
    outros = int(g.get(config.GRUPO_OUTROS, 0))
    return {
        "registros": registros,
        "presencas": presencas,
        "faltas": faltas,
        "justificadas": justificadas,
        "outros": outros,
        "pct_presenca": _pct(presencas, registros),
        "pct_falta": _pct(faltas, registros),
    }


def resumo(df: pd.DataFrame) -> dict:
    """Números do topo da tela (cartões)."""
    r = _contagens(df)
    r["servidores"] = int(df["id_servidor"].nunique()) if not df.empty else 0
    r["dias_com_chamada"] = int(df["data"].nunique()) if not df.empty else 0
    return r


def _situacao(faltas: int, pct: float, registros: int) -> tuple[str, str]:
    if faltas >= config.LIMITE_ALERTA_FALTAS:
        return "Atenção", f"{faltas} faltas sem justificativa"
    return "Em dia", ""


COLUNAS_SERVIDOR = [
    "id_servidor", "nome_servidor", "matricula", "cargo_funcao", "tipo_professor", "registros",
    "presencas", "faltas", "justificadas", "outros", "pct_presenca", "situacao", "motivo",
]


def por_servidor(df: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por servidor com as contagens, % de presença e situação."""
    if df.empty:
        return pd.DataFrame(columns=COLUNAS_SERVIDOR)
    linhas = []
    for (sid, nome), parte in df.groupby(["id_servidor", "nome_servidor"], sort=False):
        c = _contagens(parte)
        situacao, motivo = _situacao(c["faltas"], c["pct_presenca"], c["registros"])
        primeira = parte.iloc[0]
        linhas.append({
            "id_servidor": int(sid), "nome_servidor": nome, "matricula": primeira.get("matricula"),
            "cargo_funcao": primeira.get("cargo_funcao"), "tipo_professor": primeira.get("tipo_professor"),
            **{k: c[k] for k in ("registros", "presencas", "faltas", "justificadas", "outros", "pct_presenca")},
            "situacao": situacao, "motivo": motivo,
        })
    out = pd.DataFrame(linhas, columns=COLUNAS_SERVIDOR)
    # quem precisa de atenção primeiro; depois mais faltas; depois nome
    out["_ordem"] = (out["situacao"] != "Atenção").astype(int)
    out["_nome"] = out["nome_servidor"].map(chave_nome)
    return out.sort_values(["_ordem", "faltas", "_nome"], ascending=[True, False, True]).drop(
        columns=["_ordem", "_nome"]).reset_index(drop=True)


def por_grupo(df: pd.DataFrame, coluna: str) -> pd.DataFrame:
    """Contagens por grupo (cargo, segmento...), ordenado do menor para o
    maior % de presença — quem está pior aparece em cima."""
    colunas = ["grupo_valor", "servidores", "registros", "presencas", "faltas", "justificadas", "outros",
               "pct_presenca", "servidores_atencao"]
    if df.empty:
        return pd.DataFrame(columns=colunas)
    ps = por_servidor(df)
    mapa = df.drop_duplicates("id_servidor").set_index("id_servidor")[coluna]
    ps["grupo_valor"] = ps["id_servidor"].map(mapa)
    linhas = []
    for valor, parte in df.groupby(coluna):
        c = _contagens(parte)
        atencao = int(((ps["grupo_valor"] == valor) & (ps["situacao"] == "Atenção")).sum())
        linhas.append({"grupo_valor": valor, "servidores": int(parte["id_servidor"].nunique()),
                       **{k: c[k] for k in colunas[2:8]}, "servidores_atencao": atencao})
    return pd.DataFrame(linhas, columns=colunas).sort_values(["pct_presenca", "grupo_valor"]).reset_index(drop=True)


def por_dia(df: pd.DataFrame) -> pd.DataFrame:
    """Quantidade de cada grupo por data (para o gráfico do dia a dia)."""
    if df.empty:
        return pd.DataFrame(columns=["data", *ORDEM_GRUPOS])
    t = df.pivot_table(index="data", columns="grupo", values="id_presenca", aggfunc="count", fill_value=0)
    for g in ORDEM_GRUPOS:
        if g not in t:
            t[g] = 0
    return t[ORDEM_GRUPOS].reset_index().sort_values("data")


def por_mes(df: pd.DataFrame) -> pd.DataFrame:
    """% de presença e contagens por mês (para a evolução)."""
    colunas = ["ano", "mes", "rotulo", "registros", "presencas", "faltas", "justificadas", "pct_presenca"]
    if df.empty:
        return pd.DataFrame(columns=colunas)
    linhas = []
    for (ano, mes), parte in df.groupby(["ano", "mes"]):
        c = _contagens(parte)
        linhas.append({"ano": int(ano), "mes": int(mes), "rotulo": f"{config.MESES_PT[int(mes)][:3]}/{int(ano)}",
                       **{k: c[k] for k in colunas[3:]}})
    return pd.DataFrame(linhas, columns=colunas).sort_values(["ano", "mes"]).reset_index(drop=True)


def ocorrencias(df: pd.DataFrame) -> pd.DataFrame:
    """Tudo que não é presença (faltas, atestados...), do mais recente ao mais antigo."""
    cols = ["data", "nome_servidor", "cargo_funcao", "status", "grupo", "observacao"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    return df[df["grupo"] != config.GRUPO_PRESENTE].sort_values(["data", "nome_servidor"],
                                                                 ascending=[False, True])[cols]


# ---------------------------------------------------------------------------
# Quadro mensal (espelho) e pendências
# ---------------------------------------------------------------------------

def chave_nome(nome) -> str:
    """Chave de ordenação que ignora acentos e maiúsculas (Úrsula fica antes de Vanessa)."""
    return unicodedata.normalize("NFKD", str(nome or "")).encode("ascii", "ignore").decode().lower()


def sigla(status: str | None) -> str:
    if not status:
        return ""
    return config.SIGLA_STATUS.get(status, status[:1].upper())


def espelho(df: pd.DataFrame, periodo: Periodo, servidores: pd.DataFrame | None = None) -> pd.DataFrame:
    """Quadro servidor × dia do mês com a letra do status (P, F, A, D...).
    `servidores` (opcional): lista de servidores que devem aparecer mesmo sem
    nenhum registro no mês (ex.: todos os ativos). Colunas: nome_servidor,
    matricula, cargo_funcao, '01'..'31', P, F, J, % presença."""
    dias = [d for d in range(1, calendar.monthrange(periodo.ano, periodo.mes)[1] + 1)]
    base = df.copy()
    if not base.empty:
        base["dia_txt"] = base["data"].map(lambda d: f"{d.day:02d}")
        base["sigla"] = base["status"].map(sigla)
    nomes = base[["id_servidor", "nome_servidor", "matricula", "cargo_funcao"]].drop_duplicates("id_servidor") \
        if not base.empty else pd.DataFrame(columns=["id_servidor", "nome_servidor", "matricula", "cargo_funcao"])
    if servidores is not None and not servidores.empty:
        extra = servidores.rename(columns={"id": "id_servidor"})[["id_servidor", "nome_servidor", "matricula",
                                                                   "cargo_funcao"]]
        nomes = pd.concat([nomes, extra[~extra["id_servidor"].isin(nomes["id_servidor"])]], ignore_index=True)
    linhas = []
    for r in nomes.sort_values("nome_servidor", key=lambda s: s.map(chave_nome)).itertuples():
        parte = base[base["id_servidor"] == r.id_servidor] if not base.empty else base
        linha = {"id_servidor": r.id_servidor, "nome_servidor": r.nome_servidor,
                 "matricula": r.matricula if isinstance(r.matricula, str) else "",
                 "cargo_funcao": r.cargo_funcao if isinstance(r.cargo_funcao, str) else ""}
        marc = dict(zip(parte["dia_txt"], parte["sigla"])) if not parte.empty else {}
        for d in dias:
            linha[f"{d:02d}"] = marc.get(f"{d:02d}", "")
        c = _contagens(parte) if not parte.empty else _contagens(pd.DataFrame(columns=["grupo"]))
        linha.update({"P": c["presencas"], "F": c["faltas"], "J": c["justificadas"],
                      "% presença": c["pct_presenca"]})
        linhas.append(linha)
    colunas = ["id_servidor", "nome_servidor", "matricula", "cargo_funcao", *[f"{d:02d}" for d in dias],
               "P", "F", "J", "% presença"]
    return pd.DataFrame(linhas, columns=colunas)


def pendencias(df: pd.DataFrame, ativos: pd.DataFrame) -> pd.DataFrame:
    """Servidores ativos sem registro em dias que tiveram chamada.
    (Um dia "teve chamada" quando alguém foi lançado nele — assim feriados
    e recessos, onde ninguém foi lançado, não viram pendência.)"""
    cols = ["data", "nome_servidor", "cargo_funcao", "tipo_professor"]
    if df.empty or ativos.empty:
        return pd.DataFrame(columns=cols)
    dias = sorted(df["data"].unique())
    feitos = set(zip(df["data"], df["id_servidor"]))
    linhas = [
        {"data": d, "nome_servidor": s.nome_servidor, "cargo_funcao": s.cargo_funcao,
         "tipo_professor": s.tipo_professor}
        for d in dias for s in ativos.itertuples() if (d, s.id) not in feitos
    ]
    return pd.DataFrame(linhas, columns=cols).sort_values(["data", "nome_servidor"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Texto em linguagem simples
# ---------------------------------------------------------------------------

def fmt_pct(v: float) -> str:
    return f"{v:.1f}%".replace(".", ",")


def fmt_data(d: dt.date) -> str:
    return d.strftime("%d/%m/%Y")


def plural(n: int, singular: str, plural_: str | None = None) -> str:
    return f"{n} {singular if n == 1 else (plural_ or singular + 's')}"


def frase_resumo(res: dict, periodo: Periodo, n_atencao: int = 0, n_pendencias: int | None = None) -> list[str]:
    """Resumo do período em frases curtas, para o topo das telas e do PDF."""
    if not res["registros"]:
        return [f"Nenhuma presença lançada em {periodo.rotulo}."]
    frases = [
        f"Em {periodo.rotulo}, a presença foi de {fmt_pct(res['pct_presenca'])} "
        f"({plural(res['dias_com_chamada'], 'dia')} com chamada, {plural(res['servidores'], 'servidor', 'servidores')}).",
    ]
    if res["faltas"] or res["justificadas"]:
        frases.append(f"Faltas: {res['faltas']} sem justificativa e {res['justificadas']} justificada(s) "
                      "(atestado/declaração).")
    else:
        frases.append("Nenhuma falta no período.")
    if n_atencao:
        frases.append(f"{plural(n_atencao, 'servidor precisa', 'servidores precisam')} de atenção "
                      f"({config.LIMITE_ALERTA_FALTAS} ou mais faltas sem justificativa).")
    else:
        frases.append("Nenhum servidor em situação de atenção.")
    if n_pendencias:
        frases.append(f"Atenção: {plural(n_pendencias, 'lançamento pendente', 'lançamentos pendentes')} "
                      "(servidor ativo sem registro em dia com chamada).")
    return frases
