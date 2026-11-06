/**
 * Vocabulario de exibicao e formatacao do despacho de expedicoes (spec 006).
 * O servidor manda o estado observado no mesmo nome que `game/expedition.py`
 * usa; aqui so se traduz o rotulo e se formatam numeros ja prontos — nunca se
 * deriva um valor novo (Artigo II), igual a `lib/mapa.ts` e `lib/treinadores.ts`.
 */
import type { EstadoObservadoExpedicao } from '@/api/tipos'

const ROTULOS_ESTADO_OBSERVADO: Record<EstadoObservadoExpedicao, string> = {
  EM_CURSO: 'Em curso',
  AGUARDANDO_RELATORIO: 'Aguardando relatorio',
  CONCLUIDA_SUCESSO: 'Concluida com sucesso',
  CONCLUIDA_FALHA: 'Concluida em falha',
  ABORTADA: 'Abortada',
}

export function rotuloEstadoObservado(estado: EstadoObservadoExpedicao): string {
  return ROTULOS_ESTADO_OBSERVADO[estado]
}

/**
 * Formata segundos (sempre nao negativos, vindos do servidor ou da contagem
 * local entre polls) como "mm:ss". Puramente apresentacional: nenhuma conta
 * de jogo acontece aqui.
 */
export function formatarTempoRestante(segundos: number): string {
  const seguro = Math.max(0, Math.round(segundos))
  const minutos = Math.floor(seguro / 60)
  const segundosRestantes = seguro % 60
  return `${String(minutos).padStart(2, '0')}:${String(segundosRestantes).padStart(2, '0')}`
}

/**
 * `chance_estimada` chega do servidor como fracao 0..1; formatar como "68%"
 * e so mudar a casa decimal para exibicao, a mesma fracao que o servidor
 * calculou (Artigo II: o cliente formata, nao deriva).
 */
export function formatarPercentual(fracao: number): string {
  return `${Math.round(fracao * 100)}%`
}
