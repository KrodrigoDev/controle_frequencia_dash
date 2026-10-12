"""Hash e verificação de senhas (PBKDF2-HMAC-SHA256, só biblioteca padrão).

A senha nunca é guardada em texto puro: o banco guarda
`pbkdf2_sha256$iterações$salt$hash`, com um salt aleatório por senha.
"""

import base64
import hashlib
import hmac
import os

ALGORITMO = "pbkdf2_sha256"
ITERACOES = 200_000


def hash_senha(senha: str) -> str:
    salt = os.urandom(16)
    derivada = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, ITERACOES)
    return "$".join(
        [
            ALGORITMO,
            str(ITERACOES),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(derivada).decode("ascii"),
        ]
    )


def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    try:
        algoritmo, iteracoes, salt_b64, hash_b64 = hash_armazenado.split("$")
        if algoritmo != ALGORITMO:
            return False
        salt = base64.b64decode(salt_b64)
        esperado = base64.b64decode(hash_b64)
        derivada = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, int(iteracoes))
        return hmac.compare_digest(derivada, esperado)
    except (ValueError, TypeError, AttributeError):
        return False
