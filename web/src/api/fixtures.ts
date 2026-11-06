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
  EntradaPokedexCapturada,
  EntradaPokedexDesconhecida,
  EntradaPokedexVista,
  ItemEmEstoque,
  PerfilCompleto,
  PokemonDetalhe,
  PokemonResumo,
  Professor,
  RespostaItens,
  RespostaListaPokemon,
  RespostaPokedex,
  ResumoLaboratorio,
  Sessao,
  StatsEfetivos,
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
