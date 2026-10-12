"""Junta banco + cálculos num "pacote" de dados por período.

As telas e as exportações (Excel/PDF) chamam as mesmas funções daqui, então
o que aparece na tela é exatamente o que vai para o arquivo.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.model import crud
from src.services import indicadores as ind
from src.services.indicadores import Periodo


@dataclass
class Pacote:
    periodo: Periodo
    titulo: str
    dados: pd.DataFrame                      # lançamentos (já filtrados)
    resumo: dict
    servidores: pd.DataFrame                 # ind.por_servidor
    frases: list[str]
    pendencias: pd.DataFrame = field(default_factory=pd.DataFrame)
    espelho: pd.DataFrame | None = None
    grupos: dict[str, pd.DataFrame] = field(default_factory=dict)  # rótulo da dimensão -> ind.por_grupo
    filtros_txt: str = ""


def carregar(periodo: Periodo) -> pd.DataFrame:
    return ind.preparar(crud.presenca_detalhada(periodo.inicio, periodo.fim))


def ativos() -> pd.DataFrame:
    return crud.list_servidores(apenas_ativos=True)


def descrever_filtros(filtros: dict) -> str:
    nomes = {v: k for k, v in ind.DIMENSOES.items()}
    partes = [f"{nomes.get(c, c)}: {', '.join(map(str, v))}" for c, v in filtros.items() if v and c in nomes]
    return " · ".join(partes) if partes else "Todos os servidores"


def montar(periodo: Periodo, filtros: dict | None = None, titulo: str = "Frequência",
           com_espelho: bool = False, com_pendencias: bool = True,
           dimensoes: list[str] | None = None) -> Pacote:
    """Monta tudo o que uma tela/relatório precisa para o período e filtros."""
    filtros = {k: v for k, v in (filtros or {}).items() if v}
    df = ind.filtrar(carregar(periodo), None, **filtros)
    res = ind.resumo(df)
    ps = ind.por_servidor(df)

    pend = pd.DataFrame()
    lista_ativos = None
    if com_pendencias or com_espelho:
        lista_ativos = ativos()
        for col, valores in filtros.items():
            if col in lista_ativos:
                lista_ativos = lista_ativos[lista_ativos[col].fillna("Não informado").isin(valores)]
    if com_pendencias:
        pend = ind.pendencias(df, lista_ativos)

    n_atencao = int((ps["situacao"] == "Atenção").sum())
    pacote = Pacote(
        periodo=periodo, titulo=titulo, dados=df, resumo=res, servidores=ps,
        frases=ind.frase_resumo(res, periodo, n_atencao, len(pend) if com_pendencias else None),
        pendencias=pend, filtros_txt=descrever_filtros(filtros),
    )
    if com_espelho and periodo.mensal:
        pacote.espelho = ind.espelho(df, periodo, lista_ativos)
    for rotulo in dimensoes or []:
        pacote.grupos[rotulo] = ind.por_grupo(df, ind.DIMENSOES[rotulo])
    return pacote


def fechamento(periodo: Periodo) -> Pacote:
    """Pacote completo do fechamento mensal."""
    return montar(periodo, titulo="Fechamento mensal de frequência", com_espelho=True,
                  dimensoes=["Cargo / função", "Segmento (professores)", "Tipo de servidor"])


def individual(periodo: Periodo, id_servidor: int) -> Pacote:
    p = montar(periodo, {"id_servidor": [id_servidor]}, titulo="Frequência individual",
               com_espelho=False, com_pendencias=False)
    return p
