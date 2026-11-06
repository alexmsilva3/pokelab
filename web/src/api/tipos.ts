/**
 * Tipos do contrato HTTP do PokeLab, espelhando o modelo de dominio da secao 3
 * do SDD e os contratos descritos em specs/002-credenciais-do-professor/plan.md.
 *
 * Os nomes de campo seguem o que o servidor envia (snake_case, como o resto
 * do dominio em portugues). Artigo II: o cliente nao deriva nem recalcula
 * nenhum desses valores, so formata.
 */

export interface Professor {
  id: string
  usuario: string
  nome_exibicao: string | null
}

export interface Laboratorio {
  id: string
  nome: string
  nivel: number
  experiencia: number
  moedas: number
  /** Quantos treinadores este nivel comporta. Derivado pelo servidor. */
  limite_treinadores: number
}

/** Contagens que o cabecalho do laboratorio precisa, prontas do servidor. */
export interface ResumoLaboratorio {
  pokemon: number
  treinadores: number
  locais_desbloqueados: number
  especies_vistas: number
  especies_capturadas: number
}

export interface Sessao {
  token: string
  professor: Professor
  laboratorio: Laboratorio
}

export interface PerfilCompleto {
  professor: Professor
  laboratorio: Laboratorio
  resumo: ResumoLaboratorio
}

// --- Acervo (spec 003) -------------------------------------------------

/**
 * Os dezoito tipos do seed (species.json), em ingles, como o servidor manda.
 * Nao sao nome proprio, mas tambem nao sao regra de jogo: e vocabulario de
 * exibicao, traduzido em src/lib/tipos.ts.
 */
export type TipoPokemon =
  | 'normal'
  | 'fire'
  | 'water'
  | 'electric'
  | 'grass'
  | 'ice'
  | 'fighting'
  | 'poison'
  | 'ground'
  | 'flying'
  | 'psychic'
  | 'bug'
  | 'rock'
  | 'ghost'
  | 'dragon'
  | 'dark'
  | 'steel'
  | 'fairy'

/**
 * Linha da lista paginada de GET /pokemon. Os campos sao planos (sem um
 * sub-objeto "especie"), espelhando app/schemas/pokemon.py::PokemonResumo:
 * o servidor ja resolve `nome` (apelido ou nome da especie, regra 4) antes
 * de mandar.
 */
export interface PokemonResumo {
  id: string
  nome: string
  /** Apelido cru; nulo quando o professor nao deu nenhum. */
  apelido: string | null
  especie_id: number
  especie_nome: string
  tipo_primario: TipoPokemon
  tipo_secundario: TipoPokemon | null
  sprite: string
  nivel: number
  atribuido: boolean
  treinador_id: string | null
}

export interface RespostaListaPokemon {
  items: PokemonResumo[]
  total: number
  page: number
  page_size: number
}

/** Os seis stats do nivel atual (SDD 4.2), ja calculados pelo servidor. */
export interface StatsEfetivos {
  hp: number
  ataque: number
  defesa: number
  ataque_especial: number
  defesa_especial: number
  velocidade: number
}

export type OrigemPokemon = 'INICIAL' | 'CAPTURADO' | 'EVOLUCAO'

/**
 * Corpo de GET /pokemon/{id} e da resposta de PATCH /pokemon/{id}.
 * `local_captura` e `treinador_nome` ja chegam como nome pronto para exibir,
 * nao como id: a ficha nao faz outra chamada para resolver quem e quem.
 */
export interface PokemonDetalhe extends PokemonResumo {
  stats: StatsEfetivos
  /** Valor absoluto, "38 / 45" com hp_maximo sendo o segundo numero. */
  hp_atual: number
  hp_maximo: number
  experiencia: number
  /** Nulo no nivel maximo: ver `nivel_maximo` para o caso de certeza. */
  experiencia_para_proximo_nivel: number | null
  nivel_maximo: boolean
  origem: OrigemPokemon
  /** Nulo para origem INICIAL: starters nao tem local de captura. */
  local_captura: string | null
  capturado_em: string | null
  treinador_nome: string | null
}

/** Corpo de PATCH /pokemon/{id}. Nulo apaga o apelido. */
export interface ApelidoEntrada {
  apelido: string | null
}

export interface EntradaPokedexDesconhecida {
  numero: number
  estado: 'DESCONHECIDA'
}

export interface EntradaPokedexVista {
  numero: number
  estado: 'VISTA'
  nome: string
  tipos: TipoPokemon[]
  sprite: string
}

export interface EntradaPokedexCapturada {
  numero: number
  estado: 'CAPTURADA'
  nome: string
  tipos: TipoPokemon[]
  sprite: string
  quantidade: number
}

/**
 * Forma variavel de proposito (plan.md): uma entrada DESCONHECIDA nao carrega
 * nome nem tipo no corpo da resposta. Nao existe um campo "nome" opcional
 * universal porque isso deixaria facil reintroduzir o vazamento que o
 * criterio 9 proibe.
 */
export type EntradaPokedex =
  | EntradaPokedexDesconhecida
  | EntradaPokedexVista
  | EntradaPokedexCapturada

export interface RespostaPokedex {
  items: EntradaPokedex[]
  capturadas: number
  vistas: number
}

export type CategoriaItem = 'POKEBOLA' | 'CURA' | 'REVIVE'

/**
 * Linha de GET /items, campos planos (app/schemas/itens.py::ItemEmEstoqueLer).
 * O servidor nunca manda item com quantidade zero (regra 11).
 */
export interface ItemEmEstoque {
  item_id: string
  nome: string
  categoria: CategoriaItem
  potencia: number
  quantidade: number
}

export interface RespostaItens {
  items: ItemEmEstoque[]
}

// --- Treinadores (spec 004) ---------------------------------------------

/**
 * Identidade visual sem arquivo (game/trainers.py::Avatar): iniciais sobre
 * uma cor, ambas derivadas do nome pelo servidor. O frontend desenha, nunca
 * busca imagem.
 */
export interface AvatarTreinador {
  iniciais: string
  cor: string
}

/** Os quatro estados do treinador (SDD 3.2), no mesmo nome da coluna. */
export type StatusTreinador = 'DISPONIVEL' | 'EM_EXPEDICAO' | 'EM_ENTREGA' | 'DESCANSANDO'

/**
 * Linha de GET /trainers. O time vem em miniatura (os mesmos campos de
 * PokemonResumo) para o cartao desenhar os sprites sem uma segunda chamada.
 */
export interface TreinadorResumo {
  id: string
  nome: string
  avatar: AvatarTreinador
  nivel: number
  experiencia: number
  status: StatusTreinador
  /** Derivado pelo servidor: o invariante 3 do SDD nao se reimplementa aqui. */
  ocupado: boolean
  /** Tamanho maximo de time, vindo do balance do servidor. */
  tamanho_maximo_time: number
  time: PokemonResumo[]
  /** CAPACIDADE_TOTAL_TREINADOR menos o tamanho do time, pronta do servidor. */
  capacidade_bagagem: number
}

export interface RespostaTreinadores {
  items: TreinadorResumo[]
}

/**
 * Corpo de GET /trainers/{id} e da resposta de PUT /trainers/{id}/team: os
 * mesmos campos da lista, mais o que so faz sentido ao abrir a ficha —
 * experiencia para o proximo nivel e o poder do time (SDD 4.3), ambos inteiros
 * ja arredondados pelo servidor.
 */
export interface TreinadorDetalhe extends TreinadorResumo {
  experiencia_para_proximo_nivel: number
  poder: number
}

/** Corpo de PUT /trainers/{id}/team e de POST /trainers/{id}/team/preview. */
export interface ComposicaoTimeEntrada {
  pokemon_ids: string[]
}

/**
 * Resposta da previa (plan.md): valida sem gravar. Quando a composicao e
 * recusada, `poder` e `capacidade_bagagem` descrevem o time ATUAL do
 * treinador, nao a composicao hipotetica — ela nao muda nada, entao nao ha
 * poder dela para mostrar. `motivo` e o texto que o servidor escreveu; a tela
 * exibe sem reescrever.
 */
export interface PreviaTime {
  poder: number
  capacidade_bagagem: number
  valido: boolean
  codigo?: string | null
  motivo?: string | null
}
