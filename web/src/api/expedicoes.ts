/**
 * Chamadas de despacho de expedicoes (spec 006). Networking puro: duracao,
 * dificuldade, chance estimada e tempo restante vem prontos do servidor
 * (Artigo II) — aqui so se monta a chamada e se tipa a resposta.
 */
import { request } from '@/api/client'
import type {
  ExpedicaoEntrada,
  ExpedicaoLer,
  PreviaExpedicao,
  RespostaExpedicoes,
  EstadoObservadoExpedicao,
} from '@/api/tipos'

/**
 * O filtro compara contra o ESTADO OBSERVADO, nao contra a coluna gravada.
 *
 * Isto ja esteve errado e custou caro: a tela pedia `status=EM_CURSO`
 * acreditando filtrar a coluna, e o servidor filtrava o estado observado.
 * No instante em que o prazo vencia a expedicao deixava de ser EM_CURSO
 * observado e SUMIA da lista — justamente quando o professor mais quer olhar
 * para ela, porque acabou de terminar.
 *
 * Por isso o parametro e uma lista: o painel de ativas pede os dois estados
 * que considera ativos, e `ESTADOS_ATIVOS` deixa isso explicito.
 */
export const ESTADOS_ATIVOS: EstadoObservadoExpedicao[] = ['EM_CURSO', 'AGUARDANDO_RELATORIO']

export function listarExpedicoes(
  estados?: EstadoObservadoExpedicao[],
  sinal?: AbortSignal,
): Promise<RespostaExpedicoes> {
  const query = estados?.length
    ? '?' + estados.map((e) => `status=${encodeURIComponent(e)}`).join('&')
    : ''
  return request<RespostaExpedicoes>(`/expeditions${query}`, { signal: sinal })
}

export function buscarExpedicao(id: string, sinal?: AbortSignal): Promise<ExpedicaoLer> {
  return request<ExpedicaoLer>(`/expeditions/${encodeURIComponent(id)}`, { signal: sinal })
}

/**
 * Valida um despacho hipotetico sem gravar nada, com a mesma funcao de
 * dominio do envio real. Chamada a cada mudanca de treinador, destino ou
 * carga; quem cancela a chamada anterior e o chamador.
 */
export function previsualizarExpedicao(
  entrada: ExpedicaoEntrada,
  sinal?: AbortSignal,
): Promise<PreviaExpedicao> {
  return request<PreviaExpedicao>('/expeditions/preview', {
    method: 'POST',
    body: JSON.stringify(entrada),
    signal: sinal,
  })
}

export function despacharExpedicao(entrada: ExpedicaoEntrada): Promise<ExpedicaoLer> {
  return request<ExpedicaoLer>('/expeditions', {
    method: 'POST',
    body: JSON.stringify(entrada),
  })
}

/** Aborta a expedicao (regra 11): o treinador volta na hora, os itens nao. */
export function abortarExpedicao(id: string): Promise<ExpedicaoLer> {
  return request<ExpedicaoLer>(`/expeditions/${encodeURIComponent(id)}`, { method: 'DELETE' })
}
