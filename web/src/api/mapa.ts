/**
 * Chamadas do mapa de Kanto (spec 005). Networking puro: estado do local,
 * origem, duracao estimada e especies avistadas vem prontos do servidor
 * (Artigo II) — aqui so se monta a chamada e se tipa a resposta.
 */
import { request } from '@/api/client'
import type { LocalDetalhado, RespostaMapa } from '@/api/tipos'

export function buscarMapa(sinal?: AbortSignal): Promise<RespostaMapa> {
  return request<RespostaMapa>('/map', { signal: sinal })
}

/**
 * Detalhe de um local, com as especies avistadas pelo laboratorio.
 *
 * `treinadorId` ausente pede a duracao base, sem desconto de nivel; o
 * servidor e quem decide o desconto quando um treinador e informado (Artigo
 * II) — aqui so se monta a query string.
 */
export function buscarLocal(
  id: string,
  treinadorId?: string,
  sinal?: AbortSignal,
): Promise<LocalDetalhado> {
  const query = treinadorId ? `?treinador_id=${encodeURIComponent(treinadorId)}` : ''
  return request<LocalDetalhado>(`/map/${encodeURIComponent(id)}${query}`, { signal: sinal })
}
