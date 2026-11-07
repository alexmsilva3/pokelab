/**
 * Respostas de exemplo da API, TIPADAS.
 *
 * Existe porque um mock escrito a mao num teste inventou um campo que o
 * servidor nunca mandou (`especies_pokedex`), o `tsc` nao reclamou — o objeto
 * literal ia para dentro de `json: async () => (...)`, que e `Promise<any>` —
 * e a tela renderizou vazio com a suite verde.
 *
 * Todo mock de resposta passa por aqui. Se o contrato do servidor mudar e os
 * tipos de `tipos.ts` forem atualizados, estes helpers quebram na compilacao
 * em vez de deixarem o teste mentir.
 */

import type {
  AvatarTreinador,
  CapturaDoRelatorio,
  EntradaPokedexCapturada,
  EntradaPokedexDesconhecida,
  EntradaPokedexVista,
  EntregaLer,
  EspecieAvistada,
  EspecieVistaNoRelatorio,
  EventoDeExpedicao,
  ExpedicaoLer,
  ExpedicaoResumo,
  GanhoDeExperiencia,
  ItemCargaLer,
  ItemDoRelatorio,
  ItemEmEstoque,
  LocalDetalhado,
  LocalNoMapa,
  PerfilCompleto,
  PokemonDetalhe,
  PokemonDoRelatorio,
  PokemonEntregueNoResultado,
  PokemonResumo,
  PreviaExpedicao,
  PreviaTime,
  Professor,
  RelatorioDeCampo,
  RequisitoLer,
  RespostaClaimExpedicao,
  RespostaClaimEntrega,
  RespostaEntregas,
  RespostaExpedicoes,
  RespostaItens,
  RespostaListaPokemon,
  RespostaMapa,
  RespostaPokedex,
  RespostaTreinadores,
  ResultadoDeEntrega,
  ResumoLaboratorio,
  Sessao,
  StatsEfetivos,
  TreinadorDetalhe,
  TreinadorResumo,
  Viveiro,
} from '@/api/tipos'

export function professorExemplo(sobrescritas: Partial<Professor> = {}): Professor {
  return { id: '1', usuario: 'ash', nome_exibicao: 'Ash', ...sobrescritas }
}

export function laboratorioExemplo(
  sobrescritas: Partial<Sessao['laboratorio']> = {},
): Sessao['laboratorio'] {
  return {
    id: '10',
    nome: 'Lab Pallet',
    nivel: 1,
    experiencia: 0,
    moedas: 0,
    limite_treinadores: 3,
    ...sobrescritas,
  }
}

export function resumoExemplo(
  sobrescritas: Partial<ResumoLaboratorio> = {},
): ResumoLaboratorio {
  return {
    pokemon: 3,
    treinadores: 1,
    locais_desbloqueados: 1,
    especies_vistas: 3,
    especies_capturadas: 3,
    ...sobrescritas,
  }
}

export function sessaoExemplo(sobrescritas: Partial<Sessao> = {}): Sessao {
  return {
    token: 'token-valido',
    professor: professorExemplo(),
    laboratorio: laboratorioExemplo(),
    ...sobrescritas,
  }
}

export function perfilExemplo(sobrescritas: Partial<PerfilCompleto> = {}): PerfilCompleto {
  return {
    professor: professorExemplo(),
    laboratorio: laboratorioExemplo(),
    resumo: resumoExemplo(),
    ...sobrescritas,
  }
}

// --- Acervo (spec 003) -------------------------------------------------
// Os campos espelham app/schemas/pokemon.py: planos, sem um sub-objeto
// "especie" — o servidor ja resolve `nome` antes de mandar (regra 4).

export function pokemonResumoExemplo(
  sobrescritas: Partial<PokemonResumo> = {},
): PokemonResumo {
  return {
    id: 'poke-1',
    nome: 'Bulbasaur',
    apelido: null,
    especie_id: 1,
    especie_nome: 'Bulbasaur',
    tipo_primario: 'grass',
    tipo_secundario: 'poison',
    sprite: '1-front.png',
    nivel: 5,
    atribuido: false,
    treinador_id: null,
    ...sobrescritas,
  }
}

export function listaPokemonExemplo(
  sobrescritas: Partial<RespostaListaPokemon> = {},
): RespostaListaPokemon {
  return {
    items: [pokemonResumoExemplo()],
    total: 1,
    page: 1,
    page_size: 20,
    ...sobrescritas,
  }
}

export function statsExemplo(sobrescritas: Partial<StatsEfetivos> = {}): StatsEfetivos {
  return {
    hp: 19,
    ataque: 9,
    defesa: 9,
    ataque_especial: 11,
    defesa_especial: 11,
    velocidade: 9,
    ...sobrescritas,
  }
}

export function pokemonDetalheExemplo(
  sobrescritas: Partial<PokemonDetalhe> = {},
): PokemonDetalhe {
  return {
    ...pokemonResumoExemplo(),
    stats: statsExemplo(),
    hp_atual: 19,
    hp_maximo: 19,
    experiencia: 40,
    experiencia_para_proximo_nivel: 60,
    nivel_maximo: false,
    origem: 'INICIAL',
    local_captura: null,
    capturado_em: '2026-01-01T12:00:00Z',
    treinador_nome: null,
    ...sobrescritas,
  }
}

export function entradaPokedexDesconhecidaExemplo(
  sobrescritas: Partial<EntradaPokedexDesconhecida> = {},
): EntradaPokedexDesconhecida {
  return { numero: 151, estado: 'DESCONHECIDA', ...sobrescritas }
}

export function entradaPokedexVistaExemplo(
  sobrescritas: Partial<EntradaPokedexVista> = {},
): EntradaPokedexVista {
  return {
    numero: 4,
    estado: 'VISTA',
    nome: 'Charmander',
    tipos: ['fire'],
    sprite: '4-front.png',
    ...sobrescritas,
  }
}

export function entradaPokedexCapturadaExemplo(
  sobrescritas: Partial<EntradaPokedexCapturada> = {},
): EntradaPokedexCapturada {
  return {
    numero: 1,
    estado: 'CAPTURADA',
    nome: 'Bulbasaur',
    tipos: ['grass', 'poison'],
    sprite: '1-front.png',
    quantidade: 1,
    ...sobrescritas,
  }
}

export function pokedexExemplo(sobrescritas: Partial<RespostaPokedex> = {}): RespostaPokedex {
  return {
    items: [
      entradaPokedexCapturadaExemplo(),
      entradaPokedexVistaExemplo(),
      entradaPokedexDesconhecidaExemplo(),
    ],
    capturadas: 1,
    vistas: 2,
    ...sobrescritas,
  }
}

export function itemEstoqueExemplo(
  sobrescritas: Partial<ItemEmEstoque> = {},
): ItemEmEstoque {
  return {
    item_id: 'poke-ball',
    nome: 'Poke Ball',
    categoria: 'POKEBOLA',
    potencia: 1,
    quantidade: 10,
    ...sobrescritas,
  }
}

export function itensExemplo(sobrescritas: Partial<RespostaItens> = {}): RespostaItens {
  return {
    items: [
      itemEstoqueExemplo(),
      itemEstoqueExemplo({ item_id: 'potion', nome: 'Potion', categoria: 'CURA', quantidade: 5 }),
      itemEstoqueExemplo({ item_id: 'revive', nome: 'Revive', categoria: 'REVIVE', quantidade: 1 }),
    ],
    ...sobrescritas,
  }
}

// --- Treinadores (spec 004) ---------------------------------------------

export function avatarTreinadorExemplo(
  sobrescritas: Partial<AvatarTreinador> = {},
): AvatarTreinador {
  return { iniciais: 'AS', cor: '#2563a8', sprite: 'treinadores/youngster.png', ...sobrescritas }
}

export function treinadorResumoExemplo(
  sobrescritas: Partial<TreinadorResumo> = {},
): TreinadorResumo {
  const status = sobrescritas.status ?? 'DISPONIVEL'
  return {
    id: 'treinador-1',
    nome: 'Ash',
    avatar: avatarTreinadorExemplo(),
    nivel: 1,
    experiencia: 0,
    status,
    // Derivado do status, como o servidor faz, para que um teste que pede
    // EM_EXPEDICAO nao precise lembrar de passar `ocupado` junto e acabe
    // montando um payload que o servidor jamais enviaria.
    ocupado: status === 'EM_EXPEDICAO' || status === 'EM_ENTREGA',
    tamanho_maximo_time: 3,
    time: [],
    capacidade_bagagem: 6,
    ...sobrescritas,
  }
}

export function respostaTreinadoresExemplo(
  sobrescritas: Partial<RespostaTreinadores> = {},
): RespostaTreinadores {
  return {
    items: [
      treinadorResumoExemplo({ id: 'treinador-1', nome: 'Ash' }),
      treinadorResumoExemplo({ id: 'treinador-2', nome: 'Misty' }),
      treinadorResumoExemplo({ id: 'treinador-3', nome: 'Brock' }),
    ],
    ...sobrescritas,
  }
}

export function treinadorDetalheExemplo(
  sobrescritas: Partial<TreinadorDetalhe> = {},
): TreinadorDetalhe {
  // As sobrescritas vao para o resumo tambem, senao campos derivados dele
  // (como `ocupado`, que sai do status) ficariam no valor padrao enquanto o
  // status pedido ja seria outro — um payload que o servidor nunca enviaria.
  return {
    ...treinadorResumoExemplo(sobrescritas),
    experiencia_para_proximo_nivel: 60,
    poder: 0,
    ...sobrescritas,
  }
}

export function previaTimeExemplo(sobrescritas: Partial<PreviaTime> = {}): PreviaTime {
  return {
    poder: 13,
    capacidade_bagagem: 5,
    valido: true,
    codigo: null,
    ...sobrescritas,
  }
}

// --- Mapa (spec 005) -----------------------------------------------------

export function localNoMapaExemplo(sobrescritas: Partial<LocalNoMapa> = {}): LocalNoMapa {
  return {
    id: 'pallet-town',
    nome: 'Pallet Town',
    tipo: 'CIDADE',
    nivel_dificuldade: 1,
    nivel_selvagem_min: 2,
    nivel_selvagem_max: 4,
    estado: 'VISITADO',
    origem_id: 'pallet-town',
    origem_nome: 'Pallet Town',
    duracao_estimada_minutos: 2,
    proximo_passo_id: null,
    proximo_passo_nome: null,
    ...sobrescritas,
  }
}

/**
 * Os dez locais da v1, no estado de um laboratorio recem-criado: so Pallet
 * Town visitada e Route 1 alcancavel (criterio 1 da spec 005). O restante
 * exige visitar Route 1 primeiro, inclusive Pewter City e Cerulean City
 * (criterios 2 e 3) — e ja sai na ordem de distancia que a tela deve respeitar.
 */
export function respostaMapaExemplo(sobrescritas: Partial<RespostaMapa> = {}): RespostaMapa {
  const foraDeAlcanceAteRoute1 = (sobrescrita: Partial<LocalNoMapa>): LocalNoMapa =>
    localNoMapaExemplo({
      estado: 'FORA_DE_ALCANCE',
      origem_id: null,
      origem_nome: null,
      duracao_estimada_minutos: null,
      proximo_passo_id: 'route-1',
      proximo_passo_nome: 'Route 1',
      ...sobrescrita,
    })

  return {
    items: [
      localNoMapaExemplo(),
      localNoMapaExemplo({
        id: 'route-1',
        nome: 'Route 1',
        tipo: 'ROTA',
        nivel_dificuldade: 1,
        nivel_selvagem_min: 2,
        nivel_selvagem_max: 5,
        estado: 'ALCANCAVEL',
        origem_id: 'pallet-town',
        origem_nome: 'Pallet Town',
        duracao_estimada_minutos: 7,
      }),
      foraDeAlcanceAteRoute1({
        id: 'viridian-city',
        nome: 'Viridian City',
        tipo: 'CIDADE',
        nivel_dificuldade: 2,
        nivel_selvagem_min: 3,
        nivel_selvagem_max: 6,
      }),
      foraDeAlcanceAteRoute1({
        id: 'route-22',
        nome: 'Route 22',
        tipo: 'ROTA',
        nivel_dificuldade: 5,
        nivel_selvagem_min: 6,
        nivel_selvagem_max: 10,
      }),
      foraDeAlcanceAteRoute1({
        id: 'route-2',
        nome: 'Route 2',
        tipo: 'ROTA',
        nivel_dificuldade: 2,
        nivel_selvagem_min: 3,
        nivel_selvagem_max: 6,
      }),
      foraDeAlcanceAteRoute1({
        id: 'viridian-forest',
        nome: 'Viridian Forest',
        tipo: 'MASMORRA',
        nivel_dificuldade: 3,
        nivel_selvagem_min: 4,
        nivel_selvagem_max: 8,
      }),
      foraDeAlcanceAteRoute1({
        id: 'pewter-city',
        nome: 'Pewter City',
        tipo: 'CIDADE',
        nivel_dificuldade: 3,
        nivel_selvagem_min: 5,
        nivel_selvagem_max: 9,
      }),
      foraDeAlcanceAteRoute1({
        id: 'route-3',
        nome: 'Route 3',
        tipo: 'ROTA',
        nivel_dificuldade: 4,
        nivel_selvagem_min: 6,
        nivel_selvagem_max: 10,
      }),
      foraDeAlcanceAteRoute1({
        id: 'mt-moon',
        nome: 'Mt. Moon',
        tipo: 'MASMORRA',
        nivel_dificuldade: 5,
        nivel_selvagem_min: 7,
        nivel_selvagem_max: 12,
      }),
      foraDeAlcanceAteRoute1({
        id: 'cerulean-city',
        nome: 'Cerulean City',
        tipo: 'CIDADE',
        nivel_dificuldade: 6,
        nivel_selvagem_min: 10,
        nivel_selvagem_max: 14,
      }),
    ],
    visitados: 1,
    total: 10,
    ...sobrescritas,
  }
}

export function especieAvistadaExemplo(
  sobrescritas: Partial<EspecieAvistada> = {},
): EspecieAvistada {
  return {
    especie_id: 16,
    nome: 'Pidgey',
    sprite: '16-front.png',
    vezes_visto: 3,
    primeiro_visto_em: '2026-01-01T12:00:00Z',
    ...sobrescritas,
  }
}

export function localDetalhadoExemplo(
  sobrescritas: Partial<LocalDetalhado> = {},
): LocalDetalhado {
  return {
    ...localNoMapaExemplo(),
    encontros_base: 2,
    especies_avistadas: [especieAvistadaExemplo()],
    ...sobrescritas,
  }
}

// --- Expedicoes (spec 006) ------------------------------------------------

export function itemCargaLerExemplo(sobrescritas: Partial<ItemCargaLer> = {}): ItemCargaLer {
  return {
    item_id: 'potion',
    nome: 'Potion',
    quantidade_levada: 2,
    quantidade_consumida: 0,
    ...sobrescritas,
  }
}

/**
 * Uma expedicao em curso, a meio caminho do prazo. `segundos_restantes` e
 * `estado_observado` sao os dois campos que o servidor recalcula a cada
 * leitura (plan.md) — testes de contador sobrescrevem so `segundos_restantes`.
 *
 * `seed` usa um valor ACIMA de 2**53-1 de proposito (revisao da Fase 7,
 * achado 2): um numero pequeno aqui escondia exatamente o defeito que motivou
 * a troca do tipo para string — nenhum teste via a semente truncada porque a
 * fixture nunca exercitava uma magnitude real. `RespostaExpedicoes.items` usa
 * `ExpedicaoResumo` (achado 1: a listagem nao traz `relatorio`); esta funcao
 * devolve a ficha completa (`ExpedicaoLer`), usada por `GET /expeditions/{id}`
 * e pelo `claim`.
 */
export function expedicaoResumoExemplo(sobrescritas: Partial<ExpedicaoResumo> = {}): ExpedicaoResumo {
  return {
    id: 'expedicao-1',
    treinador_id: 'treinador-1',
    treinador_nome: 'Ash',
    local_destino_id: 'route-1',
    local_destino_nome: 'Route 1',
    local_origem_id: 'pallet-town',
    local_origem_nome: 'Pallet Town',
    status: 'EM_CURSO',
    estado_observado: 'EM_CURSO',
    seed: '3500104150819416180',
    started_at: '2026-01-01T12:00:00Z',
    eta: '2026-01-01T12:07:00Z',
    resolvida_em: null,
    segundos_restantes: 210,
    duracao_minutos: 7,
    dificuldade_calculada: 4,
    poder_time_calculado: 13,
    carga: [],
    ...sobrescritas,
  }
}

/**
 * `relatorio` vem nulo, como toda expedicao ainda `EM_CURSO`; testes de
 * relatorio sobrescrevem junto com um estado terminal.
 */
export function expedicaoLerExemplo(sobrescritas: Partial<ExpedicaoLer> = {}): ExpedicaoLer {
  const { relatorio = null, ...resumoSobrescritas } = sobrescritas
  return {
    ...expedicaoResumoExemplo(resumoSobrescritas),
    relatorio,
  }
}

export function respostaExpedicoesExemplo(
  sobrescritas: Partial<RespostaExpedicoes> = {},
): RespostaExpedicoes {
  return {
    items: [expedicaoResumoExemplo()],
    total: 1,
    ...sobrescritas,
  }
}

export function previaExpedicaoExemplo(
  sobrescritas: Partial<PreviaExpedicao> = {},
): PreviaExpedicao {
  return {
    duracao_minutos: 7,
    eta_estimado: '2026-01-01T12:07:00Z',
    dificuldade: 4,
    chance_estimada: 0.68,
    capacidade_bagagem: 5,
    valido: true,
    codigo: null,
    motivo: null,
    ...sobrescritas,
  }
}

// --- Relatorio de campo (spec 007) ----------------------------------------

export function eventoDeExpedicaoExemplo(
  sobrescritas: Partial<EventoDeExpedicao> = {},
): EventoDeExpedicao {
  return {
    ordem: 0,
    tipo: 'PARTIDA',
    texto: 'Ash partiu de Pallet Town rumo a Route 1.',
    ocorrido_em_minuto: 0,
    payload: null,
    ...sobrescritas,
  }
}

export function capturaDoRelatorioExemplo(
  sobrescritas: Partial<CapturaDoRelatorio> = {},
): CapturaDoRelatorio {
  return {
    especie_id: 10,
    especie_nome: 'Caterpie',
    nivel: 5,
    pokemon_id: 'poke-captura-1',
    ...sobrescritas,
  }
}

export function pokemonDoRelatorioExemplo(
  sobrescritas: Partial<PokemonDoRelatorio> = {},
): PokemonDoRelatorio {
  return {
    pokemon_id: 'poke-1',
    especie_id: 1,
    especie_nome: 'Bulbasaur',
    nivel_antes: 5,
    nivel_depois: 7,
    exp_ganha: 112,
    hp_antes_pct: 100,
    hp_depois_pct: 74,
    evoluiu_para_id: null,
    evoluiu_para_nome: null,
    ...sobrescritas,
  }
}

export function ganhoDeExperienciaExemplo(
  sobrescritas: Partial<GanhoDeExperiencia> = {},
): GanhoDeExperiencia {
  return { nivel_antes: 1, nivel_depois: 2, exp_ganha: 64, ...sobrescritas }
}

export function itemDoRelatorioExemplo(
  sobrescritas: Partial<ItemDoRelatorio> = {},
): ItemDoRelatorio {
  return { item_id: 'poke-ball', nome: 'Poke Ball', quantidade: 3, ...sobrescritas }
}

export function especieVistaNoRelatorioExemplo(
  sobrescritas: Partial<EspecieVistaNoRelatorio> = {},
): EspecieVistaNoRelatorio {
  return { especie_id: 10, nome: 'Caterpie', primeira_vez: true, ...sobrescritas }
}

/**
 * Uma expedicao bem-sucedida completa: partida, uma batalha vencida e o
 * retorno, com uma captura, um Pokemon que subiu de nivel, as tres
 * experiencias e um item de cada lado (consumido e encontrado). Cobre o que
 * a tela de relatorio precisa mostrar sem exigir sobrescrita na maioria dos
 * testes.
 */
export function relatorioDeCampoExemplo(
  sobrescritas: Partial<RelatorioDeCampo> = {},
): RelatorioDeCampo {
  return {
    status: 'CONCLUIDA_SUCESSO',
    resolvida_em: '2026-01-01T12:40:00Z',
    encontros: 5,
    vitorias: 4,
    derrotas: 1,
    local_desbloqueado: true,
    eventos: [
      eventoDeExpedicaoExemplo(),
      eventoDeExpedicaoExemplo({
        ordem: 1,
        tipo: 'BATALHA',
        texto: 'Bulbasaur enfrentou Caterpie (nivel 5) e venceu.',
        ocorrido_em_minuto: 3,
        payload: {
          especie_id: 10,
          especie_nome: 'Caterpie',
          nivel_selvagem: 5,
          venceu: true,
          chance: 0.72,
          exp_da_batalha: 28,
        },
      }),
      eventoDeExpedicaoExemplo({
        ordem: 2,
        tipo: 'RETORNO',
        texto: 'Ash retornou a Pallet Town.',
        ocorrido_em_minuto: 7,
      }),
    ],
    capturas: [capturaDoRelatorioExemplo()],
    time: [pokemonDoRelatorioExemplo()],
    treinador: ganhoDeExperienciaExemplo(),
    laboratorio: ganhoDeExperienciaExemplo({ nivel_antes: 1, nivel_depois: 1, exp_ganha: 160 }),
    itens_consumidos: [itemDoRelatorioExemplo()],
    itens_encontrados: [
      itemDoRelatorioExemplo({ item_id: 'potion', nome: 'Potion', quantidade: 1 }),
    ],
    especies_vistas: [especieVistaNoRelatorioExemplo()],
    ...sobrescritas,
  }
}

/**
 * Resposta de `POST /expeditions/{id}/claim`. O servidor manda o relatorio
 * duas vezes — dentro de `expedicao.relatorio` e solto em `relatorio`
 * (schemas/expedicoes.py::ExpedicaoClaimLer) — e esta fixture repete isso de
 * proposito: e o que permite `CartaoExpedicao.tsx` navegar com `expedicao` ja
 * pronta para `RelatorioDeCampo.tsx`, sem um segundo `GET`.
 */
export function respostaClaimExpedicaoExemplo(
  sobrescritas: Partial<RespostaClaimExpedicao> = {},
): RespostaClaimExpedicao {
  const relatorio = relatorioDeCampoExemplo()
  return {
    expedicao: expedicaoLerExemplo({
      status: 'CONCLUIDA_SUCESSO',
      estado_observado: 'CONCLUIDA_SUCESSO',
      segundos_restantes: null,
      resolvida_em: relatorio.resolvida_em,
      relatorio,
    }),
    relatorio,
    ...sobrescritas,
  }
}

// --- Viveiro e Central de Entregas (spec 008) -----------------------------

export function viveiroExemplo(sobrescritas: Partial<Viveiro> = {}): Viveiro {
  return {
    capacidade: 50,
    ocupacao: 3,
    transbordado: false,
    lugares_faltando: 0,
    items: [pokemonResumoExemplo()],
    ...sobrescritas,
  }
}

export function requisitoLerExemplo(sobrescritas: Partial<RequisitoLer> = {}): RequisitoLer {
  return {
    especie_id: 16,
    especie_nome: 'Pidgey',
    quantidade: 2,
    disponiveis_no_viveiro: 4,
    ...sobrescritas,
  }
}

/**
 * Um pedido `DISPONIVEL` e atendivel: o caso comum, usado pela maioria dos
 * testes da Central de Entregas. `eta`, `segundos_restantes` e
 * `treinador_id` nulos, como todo pedido que ainda nao foi aceito.
 */
export function entregaLerExemplo(sobrescritas: Partial<EntregaLer> = {}): EntregaLer {
  return {
    id: 'entrega-1',
    titulo: 'Encomenda para Cerulean City',
    local_destino_id: 'cerulean-city',
    local_destino_nome: 'Cerulean City',
    estado_observado: 'DISPONIVEL',
    segundos_para_expirar: 7200,
    requisitos: [requisitoLerExemplo()],
    atendivel: true,
    motivo: null,
    duracao_minutos: 12,
    recompensa_moedas: 240,
    recompensa_exp_laboratorio: 160,
    recompensa_exp_treinador: 40,
    eta: null,
    segundos_restantes: null,
    treinador_id: null,
    ...sobrescritas,
  }
}

export function respostaEntregasExemplo(
  sobrescritas: Partial<RespostaEntregas> = {},
): RespostaEntregas {
  return {
    items: [entregaLerExemplo()],
    vagas_para_repor: 0,
    segundos_para_regerar: 900,
    ...sobrescritas,
  }
}

export function pokemonEntregueNoResultadoExemplo(
  sobrescritas: Partial<PokemonEntregueNoResultado> = {},
): PokemonEntregueNoResultado {
  return { especie_nome: 'Pidgey', nivel: 4, ...sobrescritas }
}

export function resultadoDeEntregaExemplo(
  sobrescritas: Partial<ResultadoDeEntrega> = {},
): ResultadoDeEntrega {
  return {
    pokemon_entregues: [pokemonEntregueNoResultadoExemplo()],
    moedas_ganhas: 240,
    moedas_total: 1240,
    laboratorio: ganhoDeExperienciaExemplo({ nivel_antes: 2, nivel_depois: 2, exp_ganha: 160 }),
    treinador: ganhoDeExperienciaExemplo({ nivel_antes: 3, nivel_depois: 3, exp_ganha: 40 }),
    lugares_liberados: 2,
    ...sobrescritas,
  }
}

/**
 * Resposta de `POST /deliveries/{id}/claim`. Como em
 * `respostaClaimExpedicaoExemplo`, `entrega` ja vem no estado `CONCLUIDA`
 * coerente com o `resultado` — uma fixture que misturasse `DISPONIVEL` com um
 * resultado preenchido não corresponde a nada que o servidor realmente envia.
 */
export function respostaClaimEntregaExemplo(
  sobrescritas: Partial<RespostaClaimEntrega> = {},
): RespostaClaimEntrega {
  return {
    entrega: entregaLerExemplo({
      estado_observado: 'CONCLUIDA',
      segundos_para_expirar: null,
      atendivel: false,
      motivo: null,
    }),
    resultado: resultadoDeEntregaExemplo(),
    ...sobrescritas,
  }
}

/** Envelope de erro da API, no formato que main.py monta. */
export interface EnvelopeErroExemplo {
  erro: { codigo: string; mensagem: string; detalhes?: unknown }
}

/**
 * Erro no formato real do servidor.
 *
 * Existe pelo mesmo motivo das demais fixtures: escrever o envelope a mao em
 * cada teste deixa o formato divergir do que `app/main.py` realmente monta sem
 * que nada acuse.
 */
export function erroExemplo(
  codigo = 'ERRO_INTERNO',
  mensagem = 'Falha ao consultar o laboratorio.',
  detalhes?: unknown,
): EnvelopeErroExemplo {
  return { erro: detalhes === undefined ? { codigo, mensagem } : { codigo, mensagem, detalhes } }
}
