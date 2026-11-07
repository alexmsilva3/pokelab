/**
 * Vocabulario de exibicao da Central de Entregas (spec 008). O servidor
 * manda o estado observado no mesmo nome que o dominio usa; aqui so se
 * traduz o rotulo, igual a `lib/expedicoes.ts`.
 */
import type { EstadoObservadoEntrega } from '@/api/tipos'

const ROTULOS_ESTADO_ENTREGA: Record<EstadoObservadoEntrega, string> = {
  DISPONIVEL: 'Disponivel',
  EXPIRADA: 'Expirada',
  EM_CURSO: 'Em curso',
  CONCLUIDA: 'Concluida',
  DESCARTADA: 'Descartada',
}

export function rotuloEstadoEntrega(estado: EstadoObservadoEntrega): string {
  return ROTULOS_ESTADO_ENTREGA[estado]
}
