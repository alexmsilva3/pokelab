/**
 * Mapa de Kanto em SVG, reutilizavel (telas: Fase 8).
 *
 * Artigo II da constituicao: quem decide quem e alcancavel e o servidor, no
 * campo `estado` de GET /map. Este componente so DESENHA o que chegou — as
 * coordenadas e as arestas abaixo sao DESENHO, nunca dado de jogo. Elas nunca
 * decidem se um local pode ser escolhido: isso e sempre `local.estado`, lido
 * das props. Um local fora de alcance que seja vizinho (aresta) de um
 * desbloqueado continua fora de alcance — a aresta so traca a linha.
 *
 * Usado em dois lugares: leitura em pages/Mapa.tsx (clicar destaca o local,
 * no mapa E na lista ao lado, nunca navega) e selecao em
 * components/DespacharExpedicao.tsx (clicar escolhe o destino). `selecionadoId`
 * tem o MESMO efeito visual (marcador "selecionado") nos dois modos — o que
 * muda entre eles e so quem pode ser acionado (ver `podeAcionar`). Uma prop
 * que so funcionasse num modo seria uma armadilha; o professor espera ver o
 * local destacado onde quer que clique.
 *
 * Os quatro estados visuais (desbloqueado, alcancavel, fora de alcance,
 * selecionado) nunca dependem so de cor: a forma do marcador, o
 * preenchimento e a espessura do traco mudam juntos, para quem nao distingue
 * vermelho de cinza.
 *
 * Cada local e um alvo focalizavel (role="button", Tab, Enter, Espaco), com
 * rotulo que diz nome e estado. O SVG inteiro tem role e rotulo proprios. A
 * lista de locais que a tela ja mostra continua sendo a alternativa em
 * texto — este componente so se ACRESCENTA a ela, nunca a substitui. Essa
 * alternativa em texto e o que sustenta dois reforcos abaixo: um local que o
 * servidor manda e esta tabela de desenho nao conhece ganha um aviso visivel
 * em vez de sumir calado (a lista continua mostrando ele normalmente), e em
 * telas de toque o nome completo de cada ponto mora so na lista — nunca
 * atras de um hover que toque nenhum aciona.
 */
import type { KeyboardEvent, MouseEvent } from 'react'
import type { LocalNoMapa } from '@/api/tipos'
import { rotuloEstadoLocal } from '@/lib/mapa'
import { ARESTAS, COORDENADAS, RAIO_ALVO_CLIQUE, VIEWBOX } from '@/lib/mapaDesenho'

export type ModoMapaKanto = 'leitura' | 'selecao'

export interface MapaKantoProps {
  locais: LocalNoMapa[]
  modo: ModoMapaKanto
  /**
   * Qual local esta destacado agora — nos DOIS modos. No modo selecao e o
   * destino escolhido para a expedicao; no modo leitura e o local que o
   * professor clicou por ultimo, so para destaque (nunca navega). O efeito
   * visual (marcador "selecionado") e o mesmo nos dois casos.
   */
  selecionadoId?: string | null
  /**
   * No modo leitura, chamado para qualquer local — so destaca na lista,
   * nunca navega. No modo selecao, chamado so para local alcancavel ou ja
   * desbloqueado: fora de alcance nunca chama, porque nao e destino valido.
   */
  onSelecionarLocal?: (id: string) => void
}

type EstadoVisual = 'desbloqueado' | 'alcancavel' | 'fora-de-alcance' | 'selecionado'

function estadoVisual(
  local: LocalNoMapa,
  selecionadoId: string | null | undefined,
): EstadoVisual {
  if (local.id === selecionadoId) return 'selecionado'
  if (local.estado === 'VISITADO') return 'desbloqueado'
  if (local.estado === 'ALCANCAVEL') return 'alcancavel'
  return 'fora-de-alcance'
}

/**
 * So decide se o clique CONTA, nunca se o local E alcancavel — isso e
 * sempre `local.estado`, vindo do servidor. No modo leitura todo local
 * responde, porque so destaca na lista; no modo selecao, fora de alcance
 * nunca responde, porque nao e destino valido.
 */
function podeAcionar(local: LocalNoMapa, modo: ModoMapaKanto): boolean {
  return modo === 'leitura' || local.estado !== 'FORA_DE_ALCANCE'
}

function rotuloAcessivel(local: LocalNoMapa, estado: EstadoVisual): string {
  const estadoBase = rotuloEstadoLocal(local.estado).toLowerCase()
  const estadoTexto = estado === 'selecionado' ? `${estadoBase}, selecionado` : estadoBase
  return `${local.nome}, ${estadoTexto}`
}

/**
 * `locaisSemDesenho` e a divergencia entre o que o servidor mandou e o que
 * `COORDENADAS` conhece — hoje so acontece se o seed ganhar um local novo e
 * ninguem atualizar esta tabela. Em vez de `return null` calado (o bug
 * original), o mapa avisa, e a lista de locais ao lado continua mostrando o
 * local normalmente — ninguem fica sem destino, so o desenho admite que nao
 * sabe onde colocar o ponto.
 */
function textoAvisoLocaisSemDesenho(locaisSemDesenho: LocalNoMapa[]): string {
  const nomes = locaisSemDesenho.map((local) => local.nome).join(', ')
  if (locaisSemDesenho.length === 1) {
    return `O mapa nao sabe onde desenhar ${nomes}. Veja esse local na lista abaixo.`
  }
  return `O mapa nao sabe onde desenhar ${locaisSemDesenho.length} locais (${nomes}). Veja a lista completa abaixo.`
}

export function MapaKanto({
  locais,
  modo,
  selecionadoId = null,
  onSelecionarLocal,
}: MapaKantoProps) {
  const porId = new Map(locais.map((local) => [local.id, local]))
  const locaisComDesenho = locais.filter((local) => COORDENADAS[local.id] !== undefined)
  const locaisSemDesenho = locais.filter((local) => COORDENADAS[local.id] === undefined)

  function acionar(local: LocalNoMapa) {
    if (!podeAcionar(local, modo)) return
    onSelecionarLocal?.(local.id)
  }

  function aoTeclar(evento: KeyboardEvent<SVGGElement>, local: LocalNoMapa) {
    if (evento.key !== 'Enter' && evento.key !== ' ' && evento.key !== 'Spacebar') return
    evento.preventDefault()
    acionar(local)
  }

  return (
    <>
      {/* Em telas de toque nao ha hover, e o foco so chega DEPOIS que o
          professor ja tocou num ponto — entao a revelacao por hover/foco do
          rotulo (ver CSS) nunca ajuda a ESCOLHER no celular. A lista abaixo
          sempre teve o nome completo de cada local; esta dica so deixa claro
          que ela e a referencia, em vez de dez bolinhas mudas. */}
      <p className="mapa-kanto-dica-mobile">
        Os nomes completos estao na lista de locais, logo abaixo do mapa.
      </p>

      <svg
        className="mapa-kanto"
        viewBox={VIEWBOX}
        role="group"
        aria-label="Mapa de Kanto"
        preserveAspectRatio="xMidYMid meet"
      >
        {/* Arestas so desenham a ligacao entre pontos. Decorativas: quem usa
            leitor de tela ja tem o estado de cada local no rotulo do ponto. */}
        <g aria-hidden="true" className="mapa-kanto-arestas">
          {ARESTAS.map(([origemId, destinoId]) => {
            const pontoOrigem = COORDENADAS[origemId]
            const pontoDestino = COORDENADAS[destinoId]
            if (!porId.has(origemId) || !porId.has(destinoId) || !pontoOrigem || !pontoDestino) {
              return null
            }
            return (
              <line
                key={`${origemId}-${destinoId}`}
                className="mapa-aresta"
                x1={pontoOrigem.x}
                y1={pontoOrigem.y}
                x2={pontoDestino.x}
                y2={pontoDestino.y}
              />
            )
          })}
        </g>

        {locaisComDesenho.map((local) => {
          const ponto = COORDENADAS[local.id]!

          const estado = estadoVisual(local, selecionadoId)
          const acionavel = podeAcionar(local, modo)

          return (
            <g
              key={local.id}
              className={`mapa-local mapa-local--${estado}`}
              transform={`translate(${ponto.x} ${ponto.y})`}
              role="button"
              tabIndex={acionavel ? 0 : -1}
              aria-label={rotuloAcessivel(local, estado)}
              aria-disabled={acionavel ? undefined : true}
              /*
                Sempre presente, nunca condicional ao haver selecao. Com
                `undefined` enquanto nada esta escolhido, os dez pontos eram
                anunciados como botao simples e viravam botao de alternancia no
                primeiro clique — o leitor de tela descreveria a mesma coisa de
                dois jeitos conforme o momento.
              */
              aria-pressed={local.id === selecionadoId}
              onClick={(_evento: MouseEvent<SVGGElement>) => acionar(local)}
              onKeyDown={(evento) => aoTeclar(evento, local)}
            >
              {/* Alvo invisivel, maior que qualquer marcador: ver
                  RAIO_ALVO_CLIQUE. `fill: transparent` (nunca `none`) e o que
                  faz o SVG considerar o miolo clicavel, nao so o traco. */}
              <circle r={RAIO_ALVO_CLIQUE} className="mapa-local-alvo" aria-hidden="true" />
              <Marcador estado={estado} />
              <text
                className="mapa-local-rotulo"
                aria-hidden="true"
                x={0}
                y={9}
                textAnchor="middle"
              >
                {local.nome}
              </text>
            </g>
          )
        })}
      </svg>

      {locaisSemDesenho.length > 0 && (
        <p role="status" className="mapa-aviso-desenho">
          {textoAvisoLocaisSemDesenho(locaisSemDesenho)}
        </p>
      )}
    </>
  )
}

/**
 * Forma do marcador por estado, independente da cor: solido para
 * desbloqueado, losango tracejado para alcancavel, circulo fino e pontilhado
 * para fora de alcance, anel duplo para selecionado.
 */
function Marcador({ estado }: { estado: EstadoVisual }) {
  if (estado === 'desbloqueado') {
    return <circle r={4.2} className="mapa-local-marcador mapa-local-marcador--desbloqueado" />
  }

  if (estado === 'alcancavel') {
    return (
      <rect
        x={-3.2}
        y={-3.2}
        width={6.4}
        height={6.4}
        transform="rotate(45)"
        className="mapa-local-marcador mapa-local-marcador--alcancavel"
      />
    )
  }

  if (estado === 'selecionado') {
    return (
      <>
        <circle r={6.4} className="mapa-local-marcador-anel" />
        <circle r={4.2} className="mapa-local-marcador mapa-local-marcador--selecionado" />
      </>
    )
  }

  return <circle r={3} className="mapa-local-marcador mapa-local-marcador--fora-de-alcance" />
}
