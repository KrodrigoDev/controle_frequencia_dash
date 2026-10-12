from src.ui import auth
from src.ui.app import criar_app


def test_paginas_basicas():
    app = criar_app()
    cli = app.server.test_client()
    assert cli.get("/").status_code == 200
    r = cli.get("/sair")
    assert r.status_code == 302


def test_autenticacao():
    assert auth.autenticar("admin", "admin")[0] == "ok"
    assert auth.autenticar("admin", "errada")[0] == "invalido"
    assert auth.autenticar("ninguem", "x")[0] == "invalido"
