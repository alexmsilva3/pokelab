/**
 * Coordenadas de desenho do mapa de Kanto, usadas so por
 * `components/MapaKanto.tsx`. Vive num arquivo separado (em vez de dentro do
 * componente) para nao misturar export de componente com export de dado
 * constante — e para `MapaKanto.test.tsx` poder importar `COORDENADAS` sem
 * puxar nada de React.
 *
 * Grade de -14 a 114 (ver MARGEM_VIEWBOX abaixo), x para a direita e y para
 * baixo, seguindo a geografia real: sobe pela costa oeste de Pallet ate
 * Pewter, depois corre para leste ate Cerulean. Vive so aqui — o servidor
 * nunca manda posicao (Artigo II): estas coordenadas sao DESENHO, nunca dado
 * de jogo, e nunca decidem se um local pode ser escolhido.
 *
 * Exportada tambem para o teste de cobertura (MapaKanto.test.tsx) confirmar
 * que esta copia da topologia nao diverge do seed em
 * `data/seed/locations.json` — nunca para outro componente usar como dado de
 * jogo.
 */
export const COORDENADAS: Record<string, { x: number; y: number }> = {
  'pallet-town': { x: 18, y: 92 },
  'route-1': { x: 18, y: 78 },
  'viridian-city': { x: 18, y: 64 },
  'route-22': { x: 6, y: 64 },
  'route-2': { x: 18, y: 50 },
  'viridian-forest': { x: 18, y: 37 },
  'pewter-city': { x: 18, y: 24 },
  'route-3': { x: 40, y: 24 },
  'mt-moon': { x: 60, y: 24 },
  'cerulean-city': { x: 82, y: 24 },
}

/** Vizinhos do seed, so para o traco — nunca para decidir alcance. */
export const ARESTAS: ReadonlyArray<readonly [string, string]> = [
  ['pallet-town', 'route-1'],
  ['route-1', 'viridian-city'],
  ['viridian-city', 'route-22'],
  ['viridian-city', 'route-2'],
  ['route-2', 'viridian-forest'],
  ['viridian-forest', 'pewter-city'],
  ['pewter-city', 'route-3'],
  ['route-3', 'mt-moon'],
  ['mt-moon', 'cerulean-city'],
]

/**
 * O viewBox original ia de 0 a 100 encostado nos quatro lados: o rotulo de
 * Pallet Town (y=92, texto em y+9=101) e o de Route 22 (x=6, texto ancorado
 * ao centro estourando a esquerda) ficavam parcialmente fora e o `<svg>`
 * recorta por padrao (overflow:hidden). O anel de foco (outline-offset mais
 * a espessura do traco) tambem precisa de folga alem do proprio marcador.
 *
 * Em vez de corrigir so os dois pontos relatados, a margem abaixo da folga
 * a QUALQUER um dos dez — o pior caso e Pallet Town no fundo (precisa de
 * ~9 unidades para o anel de selecionado mais o foco) e Cerulean City na
 * lateral (~12 unidades para o rotulo "Cerulean City" ancorado ao centro).
 * 14 unidades de margem cobre os dois com folga; se um local novo nascer
 * colado numa borda com nome bem comprido, vale reconferir aqui.
 */
export const MARGEM_VIEWBOX = 14
export const VIEWBOX = `${-MARGEM_VIEWBOX} ${-MARGEM_VIEWBOX} ${100 + MARGEM_VIEWBOX * 2} ${100 + MARGEM_VIEWBOX * 2}`

/**
 * Raio do alvo de clique/toque invisivel que acompanha todo marcador,
 * independente do estado. Existe porque em SVG o padrao de pointer-events e
 * visiblePainted: uma forma com `fill: none` (o caso de
 * mapa-local-marcador--fora-de-alcance) so aciona o clique em cima do
 * proprio traco, nao no miolo — e mesmo os marcadores preenchidos tem so
 * uns 3 a 4.2 de raio, um alvo minusculo para um dedo.
 *
 * 5.5 fica abaixo da metade da menor distancia entre dois pontos vizinhos no
 * desenho (12, entre Viridian City e Route 22): dois alvos nunca se
 * sobrepoem e nenhum clique vaza para o local ao lado.
 */
export const RAIO_ALVO_CLIQUE = 5.5
