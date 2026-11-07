"""Testes do PokeLab.

Organizacao, depois da limpeza de duplicatas em 2026-11-06:

- `test_game_*.py`  — dominio puro, sem banco. Onde mora a maior parte da
  suite, porque e onde um erro e mais caro: uma formula de captura errada
  aparece como "o jogo ta estranho" tres fases depois.
- `test_<recurso>.py` — os criterios de aceite da spec daquela fase, pela API.
- `test_repositories_*.py` e `test_services_*.py` — o que a API nao alcanca:
  contagem de consultas (N+1) e concorrencia com threads reais.

Havia tambem `test_routers_*.py`, escritos pelos agentes de API para se
autoverificarem, cobrindo as mesmas rotas que os testes de criterio de aceite
ja cobriam — ate com nomes identicos. Removidos: a cobertura ficou em 98% com
exatamente as mesmas 45 linhas descobertas, provando que nao acrescentavam
nada. Os de repositories e services ficaram, porque testam o que cobertura de
linha nao mede.

Havia tambem `test_correcoes_revisao*.py`, um arquivo por FASE em que uma
revisao adversarial encontrou defeitos, em vez de um arquivo por ASSUNTO.
Realocados em 2026-11-07 para o arquivo tematico de cada achado (`test_auth.py`,
`test_pokemon.py`, `test_trainers.py`, `test_expedicoes.py`, `test_relatorio.py`,
`test_game_power.py`, `test_game_team.py`, `test_game_stats.py`,
`test_core_seguranca.py`, `test_kit_inicial_carga.py`, `test_services_auth.py`):
agrupar por fase escondia o assunto de quem for mexer num modulo e nao souber
em qual fase aquele bug apareceu. O comentario de cada teste movido continua
citando o achado e a fase original — essa informacao e util, so o nome do
arquivo que nao devia carregar o numero da fase.

Ao escrever teste novo, pergunte antes: isto cobre um criterio de aceite, uma
propriedade do dominio, ou uma estrutura que a API esconde? Se nao for nenhum
dos tres, provavelmente ja existe.
"""
