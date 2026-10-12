"""Regras e textos do sistema num lugar só.

Mudou alguma regra (ex.: o limite de faltas que gera alerta)? Troque aqui —
todas as telas e relatórios passam a usar o novo valor.
"""

import os

NOME_SISTEMA = "Controle de Frequência"
NOME_INSTITUICAO = os.environ.get("CF_INSTITUICAO", "Colégio")  # aparece no cabeçalho dos relatórios

MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}
DIAS_SEMANA_CURTO = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

# ---------------------------------------------------------------------------
# Como cada status de presença é contado nos indicadores
# ---------------------------------------------------------------------------
# Status que não estiverem em nenhum grupo entram como "Outros".
STATUS_PRESENTE = {"COMPARECEU"}
STATUS_FALTA = {"FALTOU"}
STATUS_JUSTIFICADO = {"ATESTADO", "DECLARAÇÃO"}

# Nome curto de cada grupo (usado em telas, Excel e PDF)
GRUPO_PRESENTE = "Presença"
GRUPO_FALTA = "Falta"
GRUPO_JUSTIFICADO = "Falta justificada"
GRUPO_OUTROS = "Outros"

# Letra usada no quadro mensal (espelho) e na legenda
SIGLA_STATUS = {
    "COMPARECEU": "P",
    "FALTOU": "F",
    "ATESTADO": "A",
    "DECLARAÇÃO": "D",
}

# Cores (as mesmas da versão anterior). Sempre acompanhadas de texto/letra.
COR_PRIMARIA = "#3064AD"
COR_PRESENTE = "#2E7D32"
COR_FALTA = "#C62828"
COR_JUSTIFICADO = "#E68A00"
COR_OUTROS = "#8A94A6"
COR_GRUPO = {
    GRUPO_PRESENTE: COR_PRESENTE,
    GRUPO_FALTA: COR_FALTA,
    GRUPO_JUSTIFICADO: COR_JUSTIFICADO,
    GRUPO_OUTROS: COR_OUTROS,
}

# ---------------------------------------------------------------------------
# Alertas
# ---------------------------------------------------------------------------
# Servidor com esta quantidade (ou mais) de faltas SEM justificativa no
# período aparece como "Atenção" nas telas e no fechamento.
# (Atestado e declaração não contam para este alerta.)
LIMITE_ALERTA_FALTAS = 3

# ---------------------------------------------------------------------------
# Autenticação / níveis de acesso
# ---------------------------------------------------------------------------
NIVEL_ADMIN = "admin"
NIVEL_OPERADOR = "operador"

NIVEIS_ACESSO = {
    NIVEL_ADMIN: "Administrador — acesso total ao sistema",
    NIVEL_OPERADOR: "Operador — faz a chamada, acompanha e exporta relatórios",
}

# Usuário criado automaticamente quando o banco não tem nenhum usuário.
# TROQUE A SENHA no primeiro acesso (menu Minha senha).
ADMIN_USERNAME_PADRAO = "admin"
ADMIN_SENHA_PADRAO = "admin"

SENHA_MINIMA = 6

# ---------------------------------------------------------------------------
# Servidor web
# ---------------------------------------------------------------------------
HOST = os.environ.get("CF_HOST", "127.0.0.1")
PORTA = int(os.environ.get("CF_PORT", "8050"))
DEBUG = os.environ.get("CF_DEBUG", "0") == "1"
