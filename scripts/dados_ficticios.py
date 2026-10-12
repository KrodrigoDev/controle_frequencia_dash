"""Gera servidores e presenças FICTÍCIOS para testar/demonstrar o sistema.

NUNCA rode no banco de produção. Uso (banco separado):
    set DATABASE_URL=sqlite:///./data/demo.db        (Windows)
    python -m scripts.dados_ficticios
"""

from __future__ import annotations

import datetime as dt
import random

from src.model import crud, init_db

NOMES = [
    "Ana Paula Souza", "Bruno Lima", "Carla Menezes", "Daniel Rocha", "Elaine Castro", "Fábio Nunes",
    "Gabriela Torres", "Helena Dias", "Igor Pacheco", "Juliana Prado", "Kátia Moura", "Lucas Ferreira",
    "Marta Ribeiro", "Nelson Araújo", "Olívia Campos", "Paulo Henrique Sá", "Quitéria Alves", "Rafael Gomes",
    "Sandra Vieira", "Tiago Barros", "Úrsula Melo", "Vanessa Lopes",
]


def popular(meses: list[tuple[int, int]], semente: int = 7) -> None:
    rnd = random.Random(semente)
    init_db.init_db()
    if not crud.list_servidores().empty:
        return
    op = {k: {v: i for i, v in crud.lookup_options(k).items()} for k in crud.LOOKUPS}
    cargos_prof = ["PROF./APOIO ADM.", "PEDAGOGA./COORD."]
    segmentos = ["CRECHE", "PRÉ ESCOLA", "FUNDAMENTAL I", "FUNDAMENTAL II", "EJA"]
    cargos_adm = ["VIGIA", "MERENDEIRA", "PORTEIRO", "AUX. DE SECRETARIA", "AUX. DE DISCIPLINA"]
    for i, nome in enumerate(NOMES):
        prof = i % 3 != 0
        crud.add_servidor({
            "matricula": f"{1000 + i}", "nome_servidor": nome.upper(), "cpf": "",
            "id_tipo_vinculo": op["tipo_vinculo"]["SP" if i % 4 else "EST"],
            "id_cargo_funcao": op["cargo_funcao"][rnd.choice(cargos_prof if prof else cargos_adm)],
            "id_carga_horaria": op["carga_horaria"][rnd.choice(["40H", "25H", "30H"])],
            "id_tipo_servidor": op["tipo_servidor"]["PROF" if prof else "ADM"],
            "id_tipo_professor": op["tipo_professor"][rnd.choice(segmentos)] if prof else None,
            "id_formacao_academica": op["formacao_academica"]["PEDAGOGIA"] if prof else None,
        })
    st = op["status_presenca"]
    ids = list(crud.list_servidores()["id"])
    faltosos = set(ids[:3])
    hoje = dt.date.today()
    for ano, mes in meses:
        d = dt.date(ano, mes, 1)
        while d.month == mes and d <= hoje:
            if d.weekday() < 5:
                lanc = []
                for sid in ids:
                    if sid == ids[-1] and d.day % 7 == 3:  # deixa pendências
                        continue
                    p = rnd.random()
                    lim = 0.15 if sid in faltosos else 0.03
                    status = "FALTOU" if p < lim else "ATESTADO" if p < lim + 0.03 else \
                        "DECLARAÇÃO" if p < lim + 0.04 else "COMPARECEU"
                    lanc.append({"id_servidor": int(sid), "id_status_presenca": st[status],
                                 "observacao": "Consulta médica" if status == "ATESTADO" else ""})
                crud.bulk_upsert_presenca(d, lanc)
            d += dt.timedelta(days=1)


if __name__ == "__main__":
    hoje = dt.date.today()
    anterior = (hoje.replace(day=1) - dt.timedelta(days=1))
    popular([(anterior.year, anterior.month), (hoje.year, hoje.month)])
    print("Dados fictícios criados.")
