import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { localNoMapaExemplo } from '@/api/fixtures'
import { MapaKanto } from '@/components/MapaKanto'
import { COORDENADAS } from '@/lib/mapaDesenho'

const CAMINHO_SEED_LOCAIS = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../../../data/seed/locations.json',
)

function locaisExemplo() {
  return [
    localNoMapaExemplo({ id: 'pallet-town', nome: 'Pallet Town', estado: 'VISITADO' }),
    localNoMapaExemplo({ id: 'route-1', nome: 'Route 1', estado: 'ALCANCAVEL' }),
    localNoMapaExemplo({ id: 'viridian-city', nome: 'Viridian City', estado: 'FORA_DE_ALCANCE' }),
  ]
}

describe('MapaKanto', () => {
  it('mostra os quatro estados com rotulo acessivel de nome e estado', () => {
    render(
      <MapaKanto
        locais={locaisExemplo()}
        modo="selecao"
        selecionadoId="route-1"
        onSelecionarLocal={vi.fn()}
      />,
    )

    expect(screen.getByRole('button', { name: 'Pallet Town, visitado' })).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Route 1, alcancavel, selecionado' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Viridian City, fora de alcance' }),
    ).toBeInTheDocument()
  })

  it('clicar num local alcancavel no modo selecao avisa o pai com o id do destino', () => {
    const onSelecionarLocal = vi.fn()
    render(
      <MapaKanto
        locais={locaisExemplo()}
        modo="selecao"
        selecionadoId={null}
        onSelecionarLocal={onSelecionarLocal}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Route 1, alcancavel' }))

    expect(onSelecionarLocal).toHaveBeenCalledWith('route-1')
  })

  it('clicar num local fora de alcance no modo selecao nao avisa o pai', () => {
    const onSelecionarLocal = vi.fn()
    render(
      <MapaKanto
        locais={locaisExemplo()}
        modo="selecao"
        selecionadoId={null}
        onSelecionarLocal={onSelecionarLocal}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Viridian City, fora de alcance' }))

    expect(onSelecionarLocal).not.toHaveBeenCalled()
  })

  it('Enter e Espaco acionam o local igual ao clique', () => {
    const onSelecionarLocal = vi.fn()
    render(
      <MapaKanto
        locais={locaisExemplo()}
        modo="selecao"
        selecionadoId={null}
        onSelecionarLocal={onSelecionarLocal}
      />,
    )

    const destino = screen.getByRole('button', { name: 'Route 1, alcancavel' })
    fireEvent.keyDown(destino, { key: 'Enter' })
    fireEvent.keyDown(destino, { key: ' ' })

    expect(onSelecionarLocal).toHaveBeenCalledTimes(2)
    expect(onSelecionarLocal).toHaveBeenCalledWith('route-1')
  })

  it('no modo leitura, clicar em qualquer local avisa o pai, mesmo fora de alcance', () => {
    const onSelecionarLocal = vi.fn()
    render(
      <MapaKanto
        locais={locaisExemplo()}
        modo="leitura"
        selecionadoId={null}
        onSelecionarLocal={onSelecionarLocal}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Viridian City, fora de alcance' }))

    expect(onSelecionarLocal).toHaveBeenCalledWith('viridian-city')
  })

  it('nao decide alcance pelas arestas do desenho: local fora de alcance vizinho de um desbloqueado continua nao selecionavel', () => {
    // Pallet Town e Route 1 sao vizinhos no desenho (aresta do seed), mas o
    // servidor manda Route 1 fora de alcance aqui de proposito — o
    // componente nao pode inventar alcance a partir da aresta que ele mesmo
    // desenha (Artigo II).
    const palletTown = localNoMapaExemplo({
      id: 'pallet-town',
      nome: 'Pallet Town',
      estado: 'VISITADO',
    })
    const route1ForaDeAlcance = localNoMapaExemplo({
      id: 'route-1',
      nome: 'Route 1',
      estado: 'FORA_DE_ALCANCE',
      origem_id: null,
      origem_nome: null,
      duracao_estimada_minutos: null,
    })
    const onSelecionarLocal = vi.fn()

    render(
      <MapaKanto
        locais={[palletTown, route1ForaDeAlcance]}
        modo="selecao"
        selecionadoId={null}
        onSelecionarLocal={onSelecionarLocal}
      />,
    )

    const route1 = screen.getByRole('button', { name: 'Route 1, fora de alcance' })
    expect(route1).toHaveAttribute('aria-disabled', 'true')
    expect(route1).toHaveAttribute('tabindex', '-1')

    fireEvent.click(route1)

    expect(onSelecionarLocal).not.toHaveBeenCalled()
  })

  it('o svg inteiro tem papel e rotulo para quem usa leitor de tela', () => {
    render(
      <MapaKanto
        locais={locaisExemplo()}
        modo="leitura"
        selecionadoId={null}
        onSelecionarLocal={vi.fn()}
      />,
    )

    expect(screen.getByRole('group', { name: 'Mapa de Kanto' })).toBeInTheDocument()
  })

  it('no modo leitura, selecionadoId tambem destaca o local no proprio mapa, nao so na lista', () => {
    // pages/Mapa.tsx usa modo="leitura" e passa selecionadoId para destacar o
    // local clicado no desenho, nao so na lista ao lado. Se a prop fosse
    // ignorada nesse modo, nenhum local apareceria marcado aqui.
    render(
      <MapaKanto
        locais={locaisExemplo()}
        modo="leitura"
        selecionadoId="route-1"
        onSelecionarLocal={vi.fn()}
      />,
    )

    const destacado = screen.getByRole('button', { name: 'Route 1, alcancavel, selecionado' })
    expect(destacado).toHaveAttribute('aria-pressed', 'true')
    expect(
      screen.getByRole('button', { name: 'Pallet Town, visitado' }),
    ).toHaveAttribute('aria-pressed', 'false')
  })

  it('todo marcador tem um alvo de clique/toque maior que o proprio desenho, nos quatro estados', () => {
    // Em SVG, uma forma com fill:none (o marcador de fora de alcance) so
    // aciona clique em cima do traco. O alvo invisivel por tras cobre essa
    // lacuna, e vale para os quatro estados de forma uniforme.
    const locais = [
      localNoMapaExemplo({ id: 'pallet-town', nome: 'Pallet Town', estado: 'VISITADO' }),
      localNoMapaExemplo({ id: 'route-1', nome: 'Route 1', estado: 'ALCANCAVEL' }),
      localNoMapaExemplo({ id: 'viridian-city', nome: 'Viridian City', estado: 'FORA_DE_ALCANCE' }),
    ]
    const { container } = render(
      <MapaKanto locais={locais} modo="selecao" selecionadoId="pallet-town" onSelecionarLocal={vi.fn()} />,
    )

    const alvos = container.querySelectorAll('.mapa-local-alvo')
    expect(alvos).toHaveLength(locais.length)
    alvos.forEach((alvo) => {
      const raio = Number(alvo.getAttribute('r'))
      // Maior que o maior marcador solido (r=4.2) e o maior lado do losango
      // (diagonal ~4.53), sem encostar no ponto vizinho mais proximo do
      // desenho real (metade de 12 = 6).
      expect(raio).toBeGreaterThan(4.53)
      expect(raio).toBeLessThan(6)
    })
  })

  it('os dez locais do desenho cabem no viewBox, incluindo rotulo e anel de foco, sem recorte', () => {
    const { container } = render(
      <MapaKanto
        locais={Object.keys(COORDENADAS).map((id) =>
          localNoMapaExemplo({ id, nome: id, estado: 'VISITADO' }),
        )}
        modo="leitura"
        selecionadoId={null}
        onSelecionarLocal={vi.fn()}
      />,
    )

    const svg = container.querySelector('svg.mapa-kanto')
    const viewBox = svg?.getAttribute('viewBox') ?? ''
    const [minX, minY, largura, altura] = viewBox.split(' ').map(Number)
    const maxX = minX + largura
    const maxY = minY + altura

    // Folga que o pior caso precisa: raio do anel de selecionado (6.4) mais
    // outline-offset e espessura do foco (~3) nos quatro lados; na lateral,
    // soma-se ainda meia largura do rotulo mais comprido ("Cerulean City",
    // ancorado ao centro); embaixo, o rotulo fica sempre abaixo do ponto
    // (offset fixo de 9), nunca acima.
    const FOLGA_MARCADOR_E_FOCO = 9.4
    const FOLGA_ROTULO_LATERAL = 13
    const FOLGA_ROTULO_ABAIXO = 11

    Object.values(COORDENADAS).forEach(({ x, y }) => {
      expect(x - minX).toBeGreaterThanOrEqual(FOLGA_ROTULO_LATERAL)
      expect(maxX - x).toBeGreaterThanOrEqual(FOLGA_ROTULO_LATERAL)
      expect(y - minY).toBeGreaterThanOrEqual(FOLGA_MARCADOR_E_FOCO)
      expect(maxY - y).toBeGreaterThanOrEqual(FOLGA_ROTULO_ABAIXO)
    })
  })

  it('local sem coordenada conhecida ganha aviso visivel em vez de sumir em silencio', () => {
    const locais = [
      localNoMapaExemplo({ id: 'pallet-town', nome: 'Pallet Town', estado: 'VISITADO' }),
      localNoMapaExemplo({ id: 'ilha-nova', nome: 'Ilha Nova', estado: 'ALCANCAVEL' }),
    ]
    render(
      <MapaKanto locais={locais} modo="leitura" selecionadoId={null} onSelecionarLocal={vi.fn()} />,
    )

    expect(screen.getByRole('status')).toHaveTextContent('Ilha Nova')
    expect(screen.queryByRole('button', { name: /Ilha Nova/ })).not.toBeInTheDocument()
    // O local conhecido continua desenhado normalmente.
    expect(screen.getByRole('button', { name: 'Pallet Town, visitado' })).toBeInTheDocument()
  })

  it('a tabela de coordenadas do desenho cobre exatamente os locais do seed de dados', () => {
    // Este e o teste mais importante dos quatro achados: a tabela de
    // coordenadas de MapaKanto.tsx e uma copia da topologia real, mantida a
    // mao. Se o seed ganhar (ou perder) um local e ninguem atualizar a
    // copia, esse teste falha alto em vez de o mapa silenciosamente
    // desenhar menos locais do que o laboratorio tem.
    const seedBruto = JSON.parse(readFileSync(CAMINHO_SEED_LOCAIS, 'utf-8')) as Array<{
      id: string
    }>
    const idsDoSeed = seedBruto.map((local) => local.id).sort()
    const idsDoDesenho = Object.keys(COORDENADAS).sort()

    expect(idsDoDesenho).toEqual(idsDoSeed)
  })
})
