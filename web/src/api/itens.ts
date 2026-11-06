import { request } from '@/api/client'
import type { RespostaItens } from '@/api/tipos'

export function listarItens(sinal?: AbortSignal): Promise<RespostaItens> {
  return request<RespostaItens>('/items', { signal: sinal })
}
