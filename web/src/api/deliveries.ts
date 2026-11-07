/**
 * Chamadas da Central de Entregas (spec 008). Networking puro: prazo,
 * atendibilidade, duracao e recompensa vem prontos do servidor (Artigo II) —
 * aqui so se monta a chamada e se tipa a resposta.
 */
import { request } from '@/api/client'
import type {
  AceiteEntregaEntrada,
  EntregaLer,
  RespostaClaimEntrega,
  RespostaEntregas,
} from '@/api/tipos'

export function listarEntregas(sinal?: AbortSignal): Promise<RespostaEntregas> {
  return request<RespostaEntregas>('/deliveries', { signal: sinal })
}

/**
 * Uma unica rota para dois gestos distintos (plan.md): repor as vagas abertas
 * por expiracao ou aceite (sem espera), ou descartar a lista inteira valida
 * (exige `INTERVALO_REGERAR_ENTREGAS`). Quem decide qual dos dois esta
 * acontecendo e o SERVIDOR, a partir de `vagas_para_repor` — a tela so chama
 * esta funcao quando um dos dois botoes correspondentes esta visivel
 * (`pages/Entregas.tsx`), nunca os dois ao mesmo tempo.
 *
 * Recusa 409 `AGUARDE_PARA_REGERAR` com os segundos que faltam, apenas quando
 * nao ha vaga a repor.
 */
export function regerarEntregas(): Promise<RespostaEntregas> {
  return request<RespostaEntregas>('/deliveries/refresh', { method: 'POST' })
}

/**
 * Aceita um pedido com os Pokemon escolhidos pelo professor (regra 20).
 *
 * Recusas 409: `ENTREGA_EXPIRADA`, `TREINADOR_OCUPADO`,
 * `POKEMON_NAO_ATENDE_AO_PEDIDO`, `POKEMON_INDISPONIVEL`, `ULTIMO_POKEMON`.
 */
export function aceitarEntrega(id: string, entrada: AceiteEntregaEntrada): Promise<EntregaLer> {
  return request<EntregaLer>(`/deliveries/${encodeURIComponent(id)}/accept`, {
    method: 'POST',
    body: JSON.stringify(entrada),
  })
}

/**
 * Reclama a conclusao da entrega (mesmo padrao do ADR-006 e do Artigo VII):
 * resolve na primeira chamada, uma segunda chamada sobre a mesma entrega
 * devolve o mesmo corpo sem escrever nada de novo. Recusa 409
 * `ENTREGA_EM_CURSO` antes do prazo vencer.
 */
export function concluirEntrega(id: string): Promise<RespostaClaimEntrega> {
  return request<RespostaClaimEntrega>(`/deliveries/${encodeURIComponent(id)}/claim`, {
    method: 'POST',
  })
}
