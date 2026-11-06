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

// --- Mapa (spec 005) -----------------------------------------------------

export type TipoLocal = 'CIDADE' | 'ROTA' | 'MASMORRA'

/** Os tres estados da regra 2 da spec 005, no mesmo nome que `game/mapa.py` usa. */
export type EstadoLocal = 'VISITADO' | 'ALCANCAVEL' | 'FORA_DE_ALCANCE'

/**
 * Linha de GET /map (plan.md, secao "Contratos de API"). `origem_id`,
 * `origem_nome` e `duracao_estimada_minutos` vem nulos quando o local esta
 * fora de alcance; `proximo_passo_id` e `proximo_passo_nome` vem nulos quando
 * ele ja e um destino valido (visitado ou alcancavel), porque nao falta nada.
 */
export interface LocalNoMapa {
  id: string
  nome: string
  tipo: TipoLocal
  nivel_dificuldade: number
  nivel_selvagem_min: number
  nivel_selvagem_max: number
  estado: EstadoLocal
  origem_id: string | null
  origem_nome: string | null
  duracao_estimada_minutos: number | null
  proximo_passo_id: string | null
  proximo_passo_nome: string | null
}

export interface RespostaMapa {
  items: LocalNoMapa[]
  /** Quantos dos locais do mapa ja foram visitados pelo laboratorio. */
  visitados: number
  total: number
}

/**
 * Uma especie avistada num local (plan.md). So aparece o que os treinadores
 * do proprio laboratorio ja avistaram ali (regra 9 da spec 005) — nunca a
 * tabela de encontros do seed, e nunca uma contagem do que falta descobrir
 * (regra 10): um local nunca visitado manda `especies_avistadas: []`, nao um
 * numero de quantas especies existem.
 */
export interface EspecieAvistada {
  especie_id: number
  nome: string
  sprite: string
  vezes_visto: number
  primeiro_visto_em: string
}

/**
 * Corpo de GET /map/{id}: os mesmos campos de LocalNoMapa, mais o que so faz
 * sentido ao abrir o local — quantos encontros a expedicao gera e o que foi
 * avistado ali.
 */
export interface LocalDetalhado extends LocalNoMapa {
  encontros_base: number
  especies_avistadas: EspecieAvistada[]
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

// --- Expedicoes (spec 006) ------------------------------------------------

/**
 * O que fica gravado na coluna `status` (SDD 3.2). `AGUARDANDO_RELATORIO`
 * NAO e um destes valores: e derivado pelo servidor a cada leitura a partir
 * do `eta`, nunca uma coluna (plan.md, "O estado que ninguem pediu").
 */
export type StatusExpedicao = 'EM_CURSO' | 'CONCLUIDA_SUCESSO' | 'CONCLUIDA_FALHA' | 'ABORTADA'

/**
 * O que a tela mostra (plan.md, `game/expedition.py::estado_observado`): a
 * mesma `EM_CURSO` gravada vira `AGUARDANDO_RELATORIO` quando o `eta` ja
 * passou. O calculo e inteiramente do servidor — o cliente nunca compara
 * `eta` com o relogio local (Artigo II).
 */
export type EstadoObservadoExpedicao =
  | 'EM_CURSO'
  | 'AGUARDANDO_RELATORIO'
  | 'CONCLUIDA_SUCESSO'
  | 'CONCLUIDA_FALHA'
  | 'ABORTADA'

/** Uma linha de carga na entrada: o que o professor propoe levar. */
export interface ItemCargaEntrada {
  item_id: string
  quantidade: number
}

/** A mesma linha como o servidor devolve, com o nome do item ja resolvido. */
export interface ItemCargaLer {
  item_id: string
  nome: string
  quantidade_levada: number
}

/** Corpo de POST /expeditions e de POST /expeditions/preview (plan.md). */
export interface ExpedicaoEntrada {
  treinador_id: string
  local_id: string
  carga: ItemCargaEntrada[]
}

/**
 * Linha de GET /expeditions e corpo de GET /expeditions/{id}, da resposta de
 * POST /expeditions e de DELETE /expeditions/{id} (plan.md). `estado_observado`
 * e `segundos_restantes` sao recalculados pelo servidor a cada leitura, nunca
 * gravados — e o que impede dois lugares da tela derivarem diferente.
 */
export interface ExpedicaoLer {
  id: string
  treinador_id: string
  treinador_nome: string
  local_destino_id: string
  local_destino_nome: string
  status: StatusExpedicao
  estado_observado: EstadoObservadoExpedicao
  started_at: string
  eta: string
  /** Nunca negativo; zero quando o prazo ja passou (plan.md). */
  segundos_restantes: number
  duracao_minutos: number
  dificuldade_calculada: number
  poder_time_calculado: number
  carga: ItemCargaLer[]
}

export interface RespostaExpedicoes {
  items: ExpedicaoLer[]
  total: number
}

/**
 * Resposta de POST /expeditions/preview (plan.md): valida sem gravar, com a
 * mesma funcao de dominio do despacho. Quando a composicao e recusada,
 * `motivo` e o texto que o SERVIDOR escreveu; a tela exibe sem reescrever, do
 * mesmo jeito que `PreviaTime` faz para o time.
 */
export interface PreviaExpedicao {
  // Todos nulos quando `valido` e falso: nao ha duracao nem chance de uma
  // composicao que o servidor recusa. Declarados como nao-anulaveis, a tela
  // desenhava "Chance estimada: 0%" ao lado do motivo da recusa.
  duracao_minutos: number | null
  eta_estimado: string | null
  dificuldade: number | null
  /** Fracao 0..1; a tela formata como percentual, nunca recalcula (Artigo II). */
  chance_estimada: number | null
  capacidade_bagagem: number | null
  valido: boolean
  codigo?: string | null
  motivo?: string | null
}
