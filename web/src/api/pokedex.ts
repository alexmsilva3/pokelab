import { request } from '@/api/client'
import type { RespostaPokedex } from '@/api/tipos'

export function buscarPokedex(sinal?: AbortSignal): Promise<RespostaPokedex> {
  return request<RespostaPokedex>('/pokedex', { signal: sinal })
}
