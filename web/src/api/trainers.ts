/**
 * Chamadas do corpo de treinadores (spec 004). Networking puro: poder do
 * time, capacidade de bagagem e validacao da composicao vem prontos do
 * servidor (Artigo II) — aqui so se monta a chamada e se tipa a resposta.
 */
import { request } from '@/api/client'
import type {
  ComposicaoTimeEntrada,
  PreviaTime,
  RespostaTreinadores,
  TreinadorDetalhe,
} from '@/api/tipos'

export function listarTreinadores(sinal?: AbortSignal): Promise<RespostaTreinadores> {
  return request<RespostaTreinadores>('/trainers', { signal: sinal })
}

export function buscarTreinador(id: string, sinal?: AbortSignal): Promise<TreinadorDetalhe> {
  return request<TreinadorDetalhe>(`/trainers/${id}`, { signal: sinal })
}

/**
 * Valida uma composicao hipotetica sem gravar nada. Chamada a cada mudanca na
 * tela de montagem; quem cancela a chamada anterior e o chamador.
 */
export function pretenderTime(
  id: string,
  pokemonIds: string[],
  sinal?: AbortSignal,
): Promise<PreviaTime> {
  const corpo: ComposicaoTimeEntrada = { pokemon_ids: pokemonIds }
  return request<PreviaTime>(`/trainers/${id}/team/preview`, {
    method: 'POST',
    body: JSON.stringify(corpo),
    signal: sinal,
  })
}

/** Substitui o time inteiro (regra 9): o que nao foi listado volta ao laboratorio. */
export function salvarTime(id: string, pokemonIds: string[]): Promise<TreinadorDetalhe> {
  const corpo: ComposicaoTimeEntrada = { pokemon_ids: pokemonIds }
  return request<TreinadorDetalhe>(`/trainers/${id}/team`, {
    method: 'PUT',
    body: JSON.stringify(corpo),
  })
}
