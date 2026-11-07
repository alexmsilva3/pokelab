/**
 * Vocabulario de exibicao da mochila (spec 003/007). O servidor manda a
 * categoria no mesmo nome da coluna ("POKEBOLA"); aqui so se traduz o que
 * cada categoria faz em campo, igual a `lib/mapa.ts` e `lib/treinadores.ts`
 * fazem com estado de local e status de treinador.
 *
 * Isto NAO e regra de jogo (Artigo II): e so o texto fixo que explica o
 * proposito de uma categoria, o mesmo para qualquer item dela, sempre. Nenhum
 * numero aqui vem de calculo do cliente — duracao, dificuldade e chance
 * continuam so na previa que o servidor manda.
 *
 * GET /items hoje nao expoe `efeito_duracao` (ele existe no seed e no
 * dominio, mas nao chega em `ItemEmEstoque` — ver pendencias da tarefa).
 * Por isso a mochila nao aponta QUAL item encurta a expedicao: so lembra que
 * a previa abaixo ja reflete qualquer efeito dos itens escolhidos.
 */
import type { CategoriaItem } from '@/api/tipos'

const DESCRICOES_CATEGORIA: Record<CategoriaItem, string> = {
  POKEBOLA: 'Captura um Pokemon selvagem encontrado em campo.',
  CURA: 'Cura HP do time durante a expedicao.',
  REVIVE: 'Reanima um Pokemon nocauteado durante a expedicao.',
}

export function descricaoCategoriaItem(categoria: CategoriaItem): string {
  return DESCRICOES_CATEGORIA[categoria]
}
