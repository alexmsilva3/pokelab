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
