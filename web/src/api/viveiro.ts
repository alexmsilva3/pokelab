/**
 * Chamadas do viveiro (spec 008). Networking puro: ocupacao, capacidade e
 * transbordo vem prontos do servidor (Artigo II) — aqui so se monta a
 * chamada e se tipa a resposta.
 */
import { request } from '@/api/client'
import type { Viveiro } from '@/api/tipos'

export function buscarViveiro(sinal?: AbortSignal): Promise<Viveiro> {
  return request<Viveiro>('/ranch', { signal: sinal })
}

/**
 * Solta um Pokemon do viveiro ou do time de um treinador disponivel
 * (plan.md). Irreversivel e sem recompensa — a confirmacao nomeando quem vai
 * embora e responsabilidade de quem chama, nao desta funcao.
 *
 * Recusas 409: `POKEMON_EM_EXPEDICAO`, `POKEMON_COMPROMETIDO`,
 * `ULTIMO_POKEMON`. O chamador mostra a mensagem que o servidor escreveu
 * (Artigo II), nunca uma propria.
 */
export function soltarPokemon(id: string): Promise<void> {
  return request<void>(`/pokemon/${encodeURIComponent(id)}`, { method: 'DELETE' })
}
