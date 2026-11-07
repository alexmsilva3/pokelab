/**
 * Vocabulario de exibicao e formatacao do despacho de expedicoes (spec 006).
 * O servidor manda o estado observado no mesmo nome que `game/expedition.py`
 * usa; aqui so se traduz o rotulo e se formatam numeros ja prontos — nunca se
 * deriva um valor novo (Artigo II), igual a `lib/mapa.ts` e `lib/treinadores.ts`.
 */
import type { EstadoObservadoExpedicao, ExpedicaoResumo } from '@/api/tipos'

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

/**
 * Quantas expedicoes o painel de historico DESENHA (Expedicoes.tsx).
 *
 * O corte de verdade agora e no servidor (revisao da Fase 7, achado 1):
 * `GET /expeditions` aceita `limite` e corta a consulta no banco
 * (`routers/expedicoes.py::listar_expedicoes`) — a tela nao baixa mais o
 * historico inteiro so para desenhar alguns cartoes. `maisRecentes` abaixo
 * so reordena e apara a resposta (ja pequena) que chega, como salvaguarda
 * contra fetch concorrente fora de ordem; nao e ela que resolve o achado.
 */
export const LIMITE_HISTORICO = 5

/**
 * Janela pedida ao servidor para o historico (Expedicoes.tsx), maior que
 * `LIMITE_HISTORICO` de proposito: o `limite` de `GET /expeditions` corta a
 * consulta ANTES do filtro de status (`services/expedicoes.py::listar`), e
 * pedir exatamente `LIMITE_HISTORICO` arriscaria devolver menos de 5
 * expedicoes terminadas sempre que houver expedicoes ativas mais recentes
 * ocupando posicoes da janela. O numero bate com o teto padrao do servidor,
 * generoso o bastante para o corpo de treinadores de um laboratorio.
 */
export const JANELA_HISTORICO = 20

/**
 * As `limite` expedicoes mais recentemente iniciadas, da mais nova para a
 * mais velha. Ordenacao e corte sao formatacao de lista, nao regra de jogo
 * (Artigo II): nenhum numero aqui vem de outro lugar que nao seja o proprio
 * `started_at` que o servidor ja mandou.
 */
export function maisRecentes(itens: ExpedicaoResumo[], limite: number): ExpedicaoResumo[] {
  return [...itens]
    .sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime())
    .slice(0, limite)
}
