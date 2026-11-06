/**
 * Vocabulario de exibicao e ordenacao do mapa de Kanto (spec 005). O servidor
 * manda estado e tipo no mesmo nome da coluna ("FORA_DE_ALCANCE"); aqui so se
 * traduz o rotulo mostrado na tela, igual a `lib/tipos.ts` e `lib/treinadores.ts`
 * fazem com tipo de Pokemon e status de treinador.
 */
import type {EstadoLocal, TipoLocal} from '@/api/tipos'

const ROTULOS_ESTADO: Record<EstadoLocal, string> = {
  VISITADO: 'Visitado',
  ALCANCAVEL: 'Alcancavel',
  FORA_DE_ALCANCE: 'Fora de alcance',
}

export function rotuloEstadoLocal(estado: EstadoLocal): string {
  return ROTULOS_ESTADO[estado]
}

const ROTULOS_TIPO_LOCAL: Record<TipoLocal, string> = {
  CIDADE: 'Cidade',
  ROTA: 'Rota',
  MASMORRA: 'Masmorra',
}

export function rotuloTipoLocal(tipo: TipoLocal): string {
  return ROTULOS_TIPO_LOCAL[tipo]
}

/**
 * A ordem do mapa e a que o servidor manda.
 *
 * Havia aqui um `ordenarPorDistancia` que reordenava pelo campo
 * `duracao_estimada_minutos`. Parecia inofensivo — "so compara numeros que ja
 * chegaram" —, mas e metrica diferente da do servidor: ele ordena por custo de
 * VIAGEM, e a duracao soma viagem MAIS exploracao do destino. Um local perto
 * com muitos encontros aparecia depois de um longe com poucos, e a tela
 * contradizia a propria ordem que a API havia escolhido.
 *
 * Reordenar no cliente e decidir no cliente, ainda que com dados prontos
 * (Artigo II). Se a ordem precisar mudar, muda em `game/mapa.py`.
 */
