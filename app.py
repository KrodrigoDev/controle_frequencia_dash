"""Ponto de entrada.

    python app.py                      → abre em http://127.0.0.1:8050
    waitress-serve --port=8050 app:server   (servidor de produção no Windows)

Endereço/porta: variáveis CF_HOST e CF_PORT (ex.: CF_HOST=0.0.0.0 para a rede local).
"""

import logging

import config
from src.ui.app import criar_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = criar_app()
server = app.server

if __name__ == "__main__":
    app.run(host=config.HOST, port=config.PORTA, debug=config.DEBUG)
