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
  /** Quanto desta linha o relatorio de campo consumiu (spec 007). Zero ate a expedicao resolver. */
  quantidade_consumida: number
}

/** Corpo de POST /expeditions e de POST /expeditions/preview (plan.md). */
export interface ExpedicaoEntrada {
  treinador_id: string
  local_id: string
  carga: ItemCargaEntrada[]
}

/**
 * Linha de GET /expeditions (revisao da Fase 7, achado 1): os mesmos campos
 * de `ExpedicaoLer`, SEM `relatorio`. A listagem e o painel que o professor
 * abre toda hora, e com o historico sem teto embutir a linha do tempo inteira
 * de cada expedicao nela multiplicava o peso da resposta por cada relatorio
 * ja gravado (schemas/expedicoes.py::ExpedicaoResumoLer). Quem quer o
 * conteudo do relatorio pede a ficha (`GET /expeditions/{id}`) ou reclama
 * (`POST /expeditions/{id}/claim`) — a listagem so diz QUE existe, atraves de
 * `estado_observado` e `status`.
 */
export interface ExpedicaoResumo {
  id: string
  treinador_id: string
  treinador_nome: string
  local_destino_id: string
  local_destino_nome: string
  local_origem_id: string
  local_origem_nome: string
  status: StatusExpedicao
  estado_observado: EstadoObservadoExpedicao
  /**
   * Semente da resolucao (Artigo III): o mesmo seed sempre produz o mesmo
   * relatorio. Chega como STRING (revisao da Fase 7, achado 2): a semente
   * real passa facilmente de 2**53-1, o maior inteiro que o `JSON.parse` do
   * navegador representa sem perda, e um `number` aqui perderia os digitos
   * finais antes mesmo de chegar ao estado do React. O campo nunca entra em
   * conta no cliente (Artigo II) — so exibicao/depuracao —, entao a string
   * nao custa nada a interface.
   */
  seed: string
  started_at: string
  eta: string
  /** Nulo ate a expedicao resolver (spec 007): so existe depois do claim. */
  resolvida_em: string | null
  duracao_minutos: number
  dificuldade_calculada: number
  poder_time_calculado: number
  /**
   * Nulo em estado terminal — o eta de uma expedicao que ja acabou nao conta
   * mais nada (schemas/expedicoes.py). Nunca negativo quando presente; zero
   * quando o prazo ja passou (plan.md).
   */
  segundos_restantes: number | null
  carga: ItemCargaLer[]
}

/**
 * Corpo de GET /expeditions/{id}, da resposta de POST /expeditions e de
 * DELETE /expeditions/{id} (plan.md, schemas/expedicoes.py::ExpedicaoLer):
 * a mesma `ExpedicaoResumo`, mais o relatorio. `estado_observado`,
 * `segundos_restantes` e `relatorio` sao recalculados ou resolvidos pelo
 * servidor a cada leitura, nunca gravados pelo cliente — e o que impede dois
 * lugares da tela derivarem diferente.
 */
export interface ExpedicaoLer extends ExpedicaoResumo {
  /**
   * Nulo ate a expedicao ser reclamada, ou para sempre numa expedicao
   * ABORTADA (spec 007, ADR-006): o relatorio so nasce em
   * `POST /expeditions/{id}/claim`, e este `GET` continua sem escrever nada.
   */
  relatorio: RelatorioDeCampo | null
}

/**
 * Resposta de GET /expeditions. Sem paginacao por pagina/tamanho (plan.md):
 * limitada por `limite` no SERVIDOR (revisao da Fase 7, achado 1) — o painel
 * sempre pede as N expedicoes mais recentes do laboratorio, nunca "a pagina
 * 7". `total` e a contagem de `items` nesta resposta, nao o total historico
 * do laboratorio.
 */
export interface RespostaExpedicoes {
  items: ExpedicaoResumo[]
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

// --- Relatorio de campo (spec 007) ----------------------------------------

/**
 * Uniao fechada em dez valores (specs/007-relatorio-de-campo/plan.md). O JSON
 * que chega em tempo de execucao nao e garantido pelo compilador: um tipo de
 * evento novo que o servidor venha a mandar amanha passa por aqui como string
 * qualquer, e `lib/relatorios.ts` tem default para nao quebrar a tela.
 */
export type TipoDeEvento =
  | 'PARTIDA'
  | 'BATALHA'
  | 'CAPTURA'
  | 'CAPTURA_FALHA'
  | 'DESCOBERTA'
  | 'ITEM'
  | 'CONTRATEMPO'
  | 'SUBIU_NIVEL'
  | 'EVOLUCAO'
  | 'RETORNO'

/**
 * Uma entrada da linha do tempo do relatorio (plan.md). `payload` varia por
 * tipo (ex.: a chance do encontro vai junto de `BATALHA`/`CONTRATEMPO`) e a
 * tela nunca depende do formato interno dele — so de `texto`, ja escrito em
 * portugues pelo servidor.
 */
export interface EventoDeExpedicao {
  ordem: number
  tipo: TipoDeEvento
  texto: string
  ocorrido_em_minuto: number
  payload: Record<string, unknown> | null
}

/** Uma captura do relatorio. O contrato nao manda sprite aqui — so o servidor decide o que expor. */
export interface CapturaDoRelatorio {
  especie_id: number
  especie_nome: string
  nivel: number
  pokemon_id: string
}

/**
 * O resumo de experiencia de um Pokemon do time (plan.md). `especie_nome` e
 * sempre a especie ANTES da expedicao; quando ha evolucao, `evoluiu_para_nome`
 * traz a especie seguinte, e a tela monta "Bulbasaur virou Ivysaur" a partir
 * dos dois campos, nunca de um unico nome final.
 */
export interface PokemonDoRelatorio {
  pokemon_id: string
  especie_id: number
  especie_nome: string
  nivel_antes: number
  nivel_depois: number
  exp_ganha: number
  hp_antes_pct: number
  hp_depois_pct: number
  evoluiu_para_id: number | null
  evoluiu_para_nome: string | null
}

/** Ganho de experiencia do treinador ou do laboratorio (plan.md), mesma forma para os dois. */
export interface GanhoDeExperiencia {
  nivel_antes: number
  nivel_depois: number
  exp_ganha: number
}

/** Uma linha de item consumido ou encontrado no relatorio (plan.md). */
export interface ItemDoRelatorio {
  item_id: string
  nome: string
  quantidade: number
}

/** Uma especie enfrentada na expedicao, com `primeira_vez` marcando a descoberta (plan.md). */
export interface EspecieVistaNoRelatorio {
  especie_id: number
  nome: string
  primeira_vez: boolean
}

/**
 * Corpo de `relatorio` em `POST /expeditions/{id}/claim` e em
 * `GET /expeditions/{id}` (plan.md, secao "Contratos de API"). So existe para
 * uma expedicao ja resolvida: o status aqui e sempre um dos dois terminais de
 * resolucao, nunca `EM_CURSO` nem `ABORTADA` (uma expedicao abortada nunca
 * chega a `resolver()` e por isso nunca tem relatorio).
 */
export interface RelatorioDeCampo {
  status: Extract<StatusExpedicao, 'CONCLUIDA_SUCESSO' | 'CONCLUIDA_FALHA'>
  resolvida_em: string
  encontros: number
  vitorias: number
  derrotas: number
  local_desbloqueado: boolean
  eventos: EventoDeExpedicao[]
  capturas: CapturaDoRelatorio[]
  time: PokemonDoRelatorio[]
  treinador: GanhoDeExperiencia
  laboratorio: GanhoDeExperiencia
  itens_consumidos: ItemDoRelatorio[]
  itens_encontrados: ItemDoRelatorio[]
  especies_vistas: EspecieVistaNoRelatorio[]
}

/**
 * Corpo de `POST /expeditions/{id}/claim` (plan.md). Uma segunda chamada
 * sobre a mesma expedicao devolve exatamente o mesmo corpo, sem escrever nada
 * de novo (idempotencia, Artigo VII) — por isso a tela pode tratar a resposta
 * sempre do mesmo jeito, resolva ela agora ou so releia o que ja existia.
 *
 * `expedicao.relatorio` ja vem preenchido com o mesmo conteudo de
 * `relatorio` — o servidor manda os dois (schemas/expedicoes.py::ExpedicaoClaimLer).
 * Por isso `ExpedicaoLer` sozinho (com `relatorio` dentro) basta para
 * alimentar a tela do relatorio sem um `GET` extra: ver `CartaoExpedicao.tsx`.
 */
export interface RespostaClaimExpedicao {
  expedicao: ExpedicaoLer
  relatorio: RelatorioDeCampo
}
