"""Testes do PokeLab.

Organizacao, depois da limpeza de duplicatas em 2026-11-06:

- `test_game_*.py`  — dominio puro, sem banco. Onde mora a maior parte da
  suite, porque e onde um erro e mais caro: uma formula de captura errada
  aparece como "o jogo ta estranho" tres fases depois.
- `test_<recurso>.py` — os criterios de aceite da spec daquela fase, pela API.
- `test_repositories_*.py` e `test_services_*.py` — o que a API nao alcanca:
  contagem de consultas (N+1) e concorrencia com threads reais.
- `test_correcoes_revisao*.py` — regressao dos defeitos que a revisao
  adversarial encontrou, um teste por achado.

Havia tambem `test_routers_*.py`, escritos pelos agentes de API para se
autoverificarem, cobrindo as mesmas rotas que os testes de criterio de aceite
ja cobriam — ate com nomes identicos. Removidos: a cobertura ficou em 98% com
exatamente as mesmas 45 linhas descobertas, provando que nao acrescentavam
nada. Os de repositories e services ficaram, porque testam o que cobertura de
linha nao mede.

Ao escrever teste novo, pergunte antes: isto cobre um criterio de aceite, uma
propriedade do dominio, ou uma estrutura que a API esconde? Se nao for nenhum
dos tres, provavelmente ja existe.
"""
