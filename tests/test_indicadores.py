import datetime as dt

import pandas as pd

import config
from src.services import indicadores as ind
from src.services import relatorios as rel


def _df(linhas):
    base = {"id_presenca": 0, "matricula": "", "cargo_funcao": "X", "tipo_servidor": "ADM", "tipo_professor": None,
            "tipo_vinculo": "SP", "carga_horaria": "40H", "observacao": "", "ativo": True}
    rows = []
    for i, (sid, nome, data, status) in enumerate(linhas):
        rows.append({**base, "id_presenca": i, "id_servidor": sid, "nome_servidor": nome, "data": data,
                     "ano": data.year, "mes": data.month, "dia": data.day, "fim_de_semana": data.weekday() >= 5,
                     "status": status})
    return ind.preparar(pd.DataFrame(rows))


D1, D2, D3 = dt.date(2026, 4, 1), dt.date(2026, 4, 2), dt.date(2026, 4, 3)


def test_grupos_de_status():
    assert ind.grupo_do_status("COMPARECEU") == config.GRUPO_PRESENTE
    assert ind.grupo_do_status("FALTOU") == config.GRUPO_FALTA
    assert ind.grupo_do_status("ATESTADO") == config.GRUPO_JUSTIFICADO
    assert ind.grupo_do_status("QUALQUER") == config.GRUPO_OUTROS


def test_resumo_e_atencao():
    df = _df([(1, "ANA", D1, "FALTOU"), (1, "ANA", D2, "FALTOU"), (1, "ANA", D3, "FALTOU"),
              (2, "BIA", D1, "ATESTADO"), (2, "BIA", D2, "ATESTADO"), (2, "BIA", D3, "ATESTADO")])
    r = ind.resumo(df)
    assert (r["registros"], r["presencas"], r["faltas"], r["justificadas"]) == (6, 0, 3, 3)
    ps = ind.por_servidor(df).set_index("nome_servidor")
    assert ps.loc["ANA", "situacao"] == "Atenção"   # 3 faltas sem justificativa
    assert ps.loc["BIA", "situacao"] == "Em dia"    # atestado não gera atenção


def test_pendencias_so_em_dias_com_chamada():
    df = _df([(1, "ANA", D1, "COMPARECEU"), (2, "BIA", D1, "COMPARECEU"), (1, "ANA", D2, "COMPARECEU")])
    ativos = pd.DataFrame([{"id": 1, "nome_servidor": "ANA", "cargo_funcao": "X", "tipo_professor": None},
                           {"id": 2, "nome_servidor": "BIA", "cargo_funcao": "X", "tipo_professor": None}])
    p = ind.pendencias(df, ativos)
    assert list(zip(p["data"], p["nome_servidor"])) == [(D2, "BIA")]  # D3 não teve chamada: não é pendência


def test_espelho_tem_todos_os_dias_e_ordem_sem_acento():
    df = _df([(1, "ÚRSULA", D1, "COMPARECEU"), (2, "VANESSA", D1, "FALTOU")])
    esp = ind.espelho(df, ind.periodo_mes(2026, 4))
    assert [c for c in esp.columns if c.isdigit()] == [f"{d:02d}" for d in range(1, 31)]
    assert list(esp["nome_servidor"]) == ["ÚRSULA", "VANESSA"]
    assert esp.loc[1, "01"] == "F"


def test_periodos():
    assert ind.periodo_de_valor("m:2026-02").fim == dt.date(2026, 2, 28)
    assert ind.periodo_de_valor("a:2025").rotulo == "Ano de 2025"
    ops = ind.opcoes_periodo(dt.date(2026, 1, 5), dt.date(2026, 3, 1), hoje=dt.date(2026, 3, 10))
    assert [o["value"] for o in ops][:3] == ["m:2026-03", "m:2026-02", "m:2026-01"]


def test_fechamento_bate_com_banco(meses):
    ano, mes = meses[-1]
    pac = rel.fechamento(ind.periodo_mes(ano, mes))
    r = pac.resumo
    assert r["registros"] == r["presencas"] + r["faltas"] + r["justificadas"] + r["outros"]
    assert pac.servidores["registros"].sum() == r["registros"]
    assert pac.espelho[["P", "F", "J"]].sum().sum() == r["presencas"] + r["faltas"] + r["justificadas"]
    assert not pac.pendencias.empty  # o gerador deixa pendências de propósito
    for g in pac.grupos.values():
        assert g["registros"].sum() == r["registros"]
