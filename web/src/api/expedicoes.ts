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
  RespostaClaimExpedicao,
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

/**
 * Os tres estados terminais: o historico mostra o que ja aconteceu e nao
 * muda mais. `ABORTADA` entra aqui mesmo sem relatorio (o treinador voltou,
 * e a decisao foi do professor, nao do campo) — e e por isso que ela nunca
 * aparece em `ESTADOS_ATIVOS`.
 */
export const ESTADOS_HISTORICO: EstadoObservadoExpedicao[] = [
  'CONCLUIDA_SUCESSO',
  'CONCLUIDA_FALHA',
  'ABORTADA',
]

/**
 * `limite` acompanha o parametro de mesmo nome em `GET /expeditions`
 * (revisao da Fase 7, achado 1: `routers/expedicoes.py::listar_expedicoes`).
 * Omitido, o servidor aplica o proprio teto padrao — por isso o painel de
 * ativas (`ESTADOS_ATIVOS`) nunca precisa passar nada, e so o historico
 * (`ESTADOS_HISTORICO`, em `pages/Expedicoes.tsx`) pede um valor explicito.
 */
export function listarExpedicoes(
  estados?: EstadoObservadoExpedicao[],
  opcoes?: { limite?: number; sinal?: AbortSignal },
): Promise<RespostaExpedicoes> {
  const partes: string[] = []
  if (estados?.length) {
    partes.push(...estados.map((e) => `status=${encodeURIComponent(e)}`))
  }
  if (opcoes?.limite !== undefined) {
    partes.push(`limite=${opcoes.limite}`)
  }
  const query = partes.length ? `?${partes.join('&')}` : ''
  return request<RespostaExpedicoes>(`/expeditions${query}`, { signal: opcoes?.sinal })
}

/**
 * `ExpedicaoLer` ja traz `relatorio` (plan.md, spec 007): nulo ate a
 * expedicao ser reclamada, ou para sempre numa expedicao `ABORTADA`.
 */
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

/**
 * Reclama o relatorio de campo (spec 007, ADR-006). Resolve a expedicao na
 * primeira chamada; uma segunda chamada sobre a mesma expedicao devolve o
 * mesmo corpo sem escrever nada de novo (idempotencia, Artigo VII) — por isso
 * esta funcao pode ser chamada de novo apos uma falha de rede sem medo de
 * duplicar o resultado.
 *
 * Recusa com 409: `EXPEDICAO_EM_CURSO` quando o prazo ainda nao venceu (o
 * contador local da tela adiantou), `EXPEDICAO_ABORTADA` quando a expedicao
 * foi abortada antes de ser resolvida. O chamador mostra a mensagem que o
 * servidor escreveu, nunca uma propria (Artigo II).
 */
export function receberRelatorio(id: string): Promise<RespostaClaimExpedicao> {
  return request<RespostaClaimExpedicao>(`/expeditions/${encodeURIComponent(id)}/claim`, {
    method: 'POST',
  })
}
