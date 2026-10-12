# Controle de Frequência — versão Dash

Controle de frequência dos servidores do colégio: chamada diária, acompanhamento
(geral, por servidor e por grupo) e fechamento mensal com exportação para Excel e PDF.

Usa **o mesmo banco** da versão Streamlit (mesmas tabelas e migrações) — dá para trocar
de uma para a outra sem perder nada.

## Como rodar (Windows / PyCharm)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head            # cria/atualiza as tabelas (não apaga nada)
python -m src.model.init_db     # dados padrão + usuário admin (só cria o que faltar)
python app.py                   # abre em http://127.0.0.1:8050
```

**Login inicial: `admin` / `admin`** — troque em *Minha senha*. Enquanto for a senha padrão,
aparece um aviso no menu.

Para outras pessoas da rede acessarem: `set CF_HOST=0.0.0.0` antes de `python app.py`, ou,
em produção, `waitress-serve --port=8050 app:server`.

O banco já vem copiado da versão anterior em `data/controle_frequencia.db`. Para usar outro
arquivo ou um Postgres, defina `DATABASE_URL` antes de rodar (ex.:
`set DATABASE_URL=sqlite:///C:/caminho/controle_frequencia.db`).

## Telas

| Tela                  | Para que serve                                                                 | admin | operador |
|-----------------------|--------------------------------------------------------------------------------|:-----:|:--------:|
| Visão geral           | Frequência de todos no período, com filtros por cargo, segmento, tipo, vínculo e CH | ✅ | ✅ |
| Por servidor          | Uma pessoa: calendário do mês (ou mês a mês no ano), ocorrências, PDF individual | ✅ | ✅ |
| Por grupo             | Compara cargos, segmentos, tipos, vínculos ou carga horária; clique no grupo para ver quem está nele | ✅ | ✅ |
| Fazer chamada         | Lança ou corrige a presença de um dia; mostra quem falta lançar                | ✅ | ✅ |
| Fechamento do mês     | Confere pendências e baixa Excel completo, PDF geral e folhas individuais      | ✅ | ✅ |
| Servidores            | Cadastro, edição, desligamento (mantém histórico) e exportação do cadastro     | ✅ | ❌ |
| Tabelas de apoio      | Status, cargos, segmentos, cargas horárias, vínculos, formação                 | ✅ | ❌ |
| Usuários              | Cria usuários, define nível, desativa e redefine senha                         | ✅ | ❌ |
| Minha senha           | Cada usuário troca a própria senha                                             | ✅ | ✅ |

Em qualquer tabela "por servidor", **clicar numa pessoa abre a tela Por servidor** dela.

## Como os números são calculados (iguais na tela, no Excel e no PDF)

- **Presença** = COMPARECEU · **Falta** = FALTOU · **Falta justificada** = ATESTADO ou DECLARAÇÃO.
  Status novos criados em Tabelas de apoio entram como "Outros".
- **% de presença** = presenças ÷ dias registrados.
- **Atenção** = 3 ou mais faltas sem justificativa no período (atestado/declaração não contam).
- **Pendência** = servidor ativo sem registro num dia em que houve chamada. Dias sem nenhum
  lançamento (feriado, recesso) não viram pendência.
- Sábados/domingos só entram se alguém lançou presença neles.

Essas regras ficam em `config.py` (ex.: `LIMITE_ALERTA_FALTAS`, nome da instituição em
`NOME_INSTITUICAO` ou variável `CF_INSTITUICAO`).

## Relatórios exportados

- **Excel do fechamento**: Resumo · Por servidor · Quadro do mês (P/F/A/D por dia, colorido) ·
  Por cargo · Por segmento · Por tipo · Ocorrências · Pendências · Lançamentos.
- **PDF geral** (paisagem): números do mês, resumo em frases, quem precisa de atenção,
  tabela por servidor, quadro do mês, comparativos por grupo, pendências e campos de assinatura.
- **PDF individual**: uma folha por servidor com calendário do mês, ocorrências e assinaturas
  (um servidor ou todos de uma vez).
- Visão geral, Por servidor e Por grupo também têm botões de Excel/PDF do que está na tela.

## Estrutura

```
app.py                      entrada (python app.py / waitress-serve app:server)
config.py                   regras e textos (status, alerta, níveis, porta)
assets/                     style.css (visual) e logo.png
src/model/                  banco: models, crud, database, init_db, seguranca (hash de senha)
src/services/               cálculos e relatórios — não conhecem a tela
    indicadores.py            números (resumo, por servidor, por grupo, quadro, pendências, frases)
    relatorios.py             junta banco + cálculos num "pacote" por período
    exportar_excel.py         .xlsx formatado
    exportar_pdf.py           PDFs (reportlab)
src/ui/                     telas Dash
    app.py                    login, menu, rotas e permissões
    auth.py                   sessão (cookie assinado) e checagem de nível
    componentes.py            cartões, filtros, tabelas, gráficos, calendário
    pages/                    visao_geral, individual, grupos, chamada, fechamento, servidores, tabelas, usuarios
migrations/                 Alembic (mesmas 2 revisões da versão Streamlit)
scripts/dados_ficticios.py  gera dados de teste — NUNCA rode no banco real
tests/                      pytest (usa um banco temporário)
```

## Testes

```powershell
pip install -r requirements-dev.txt
pytest
```

## Observações

- A sessão fica num cookie assinado; a chave é criada uma vez em `data/.chave_secreta`
  (ou use a variável `CF_SECRET_KEY`). Apagar esse arquivo desconecta todo mundo.
- Toda ação de gravação confere o nível do usuário no servidor — esconder o menu não é a única proteção.
- O sistema não deixa ficar sem administrador ativo, e ninguém desativa/rebaixa o próprio usuário.
