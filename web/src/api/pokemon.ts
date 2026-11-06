/**
 * Chamadas do acervo de Pokemon (spec 003). Networking puro: filtro,
 * paginacao e stats efetivos sao decididos e calculados pelo servidor
 * (Artigo II) — aqui so se monta a query string e se tipa a resposta.
 */
import { request } from '@/api/client'
import type {
  ApelidoEntrada,
  PokemonDetalhe,
  RespostaListaPokemon,
  TipoPokemon,
} from '@/api/tipos'

export interface FiltrosListaPokemon {
  tipo?: TipoPokemon
  nivelMin?: number
  nivelMax?: number
  /** Ausente nao filtra; true so com treinador; false so no laboratorio. */
  atribuido?: boolean
  /**
   * Sem treinador e sem entrega (spec 004). Diferente de `atribuido: false`,
   * que so cobre a primeira metade e vai divergir quando a Fase 8 existir.
   */
  livre?: boolean
  page?: number
  pageSize?: number
}

function construirQuery(filtros: FiltrosListaPokemon): string {
  const parametros = new URLSearchParams()

  if (filtros.tipo) parametros.set('tipo', filtros.tipo)
  if (filtros.nivelMin !== undefined) parametros.set('nivel_min', String(filtros.nivelMin))
  if (filtros.nivelMax !== undefined) parametros.set('nivel_max', String(filtros.nivelMax))
  if (filtros.atribuido !== undefined) parametros.set('atribuido', String(filtros.atribuido))
  if (filtros.livre !== undefined) parametros.set('livre', String(filtros.livre))
  parametros.set('page', String(filtros.page ?? 1))
  parametros.set('page_size', String(filtros.pageSize ?? 24))

  return parametros.toString()
}

export function listarPokemon(
  filtros: FiltrosListaPokemon = {},
  sinal?: AbortSignal,
): Promise<RespostaListaPokemon> {
  return request<RespostaListaPokemon>(`/pokemon?${construirQuery(filtros)}`, {
    signal: sinal,
  })
}

export function buscarPokemon(id: string, sinal?: AbortSignal): Promise<PokemonDetalhe> {
  return request<PokemonDetalhe>(`/pokemon/${id}`, { signal: sinal })
}

export function atualizarApelido(
  id: string,
  apelido: string | null,
): Promise<PokemonDetalhe> {
  const corpo: ApelidoEntrada = { apelido }
  return request<PokemonDetalhe>(`/pokemon/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(corpo),
  })
}
