/**
 * Vocabulario de exibicao do status do treinador (SDD 3.2). O servidor manda
 * o status no mesmo nome da coluna ("EM_EXPEDICAO"); aqui so se traduz o
 * rotulo mostrado na tela, igual a `lib/tipos.ts` faz com o tipo de Pokemon.
 */
import type { StatusTreinador } from '@/api/tipos'

const ROTULOS_STATUS: Record<StatusTreinador, string> = {
  DISPONIVEL: 'Disponivel',
  EM_EXPEDICAO: 'Em expedicao',
  EM_ENTREGA: 'Em entrega',
  DESCANSANDO: 'Descansando',
}

export function rotuloStatus(status: StatusTreinador): string {
  return ROTULOS_STATUS[status]
}

// `statusOcupado` morava aqui e saiu: era o invariante 3 do SDD reimplementado
// no cliente, contra o Artigo II. O servidor manda `ocupado` pronto.
