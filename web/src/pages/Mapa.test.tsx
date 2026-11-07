import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  especieAvistadaExemplo,
  localDetalhadoExemplo,
  respostaMapaExemplo,
} from '@/api/fixtures'
import { Mapa } from '@/pages/Mapa'

function respostaJson(corpo: unknown, status = 200) {
  return { ok: status < 400, status, json: async () => corpo }
}

/**
 * Mock de fetch roteado por URL: a tela chama /map, /trainers e /map/{id}, e
 * um unico mockResolvedValue devolveria a mesma coisa para os tres.
 */
function criarFetchMock(rotas: {
  mapa?: unknown
  treinadores?: unknown
  detalhePorId?: Record<string, unknown>
}) {
  return vi.fn((entrada: RequestInfo | URL) => {
    const url = typeof entrada === 'string' ? entrada : entrada.toString()

    if (url.includes('/trainers')) {
      return Promise.resolve(respostaJson(rotas.treinadores ?? { items: [] }))
    }

    const casamentoDetalhe = url.match(/\/map\/([^/?]+)/)
    if (casamentoDetalhe) {
      const id = casamentoDetalhe[1]
      const corpo = rotas.detalhePorId?.[id] ?? localDetalhadoExemplo({ id })
      return Promise.resolve(respostaJson(corpo))
    }

    if (url.includes('/map')) {
      return Promise.resolve(respostaJson(rotas.mapa ?? respostaMapaExemplo()))
    }

    throw new Error(`URL nao mapeada no mock: ${url}`)
  })
}

function renderMapa() {
  return render(
    <MemoryRouter>
      <Mapa />
    </MemoryRouter>,
  )
}

/**
 * A tela ganhou um mapa interativo acima da lista (ambos mostram o nome de
 * cada local), entao toda consulta de cartao precisa ficar escopada a lista
 * — senao casa tambem com o ponto homonimo do mapa.
 */
function obterListaLocais() {
  return screen.getByRole('list', { name: 'Lista de locais' })
}

/**
 * O cartao cujo nome e exatamente `nome`, nao apenas um cartao cujo texto o
 * menciona de passagem — um local fora de alcance cita "Route 1" na frase
 * "Visite Route 1 antes.", e `getByRole` por nome acessivel casaria com os
 * dois.
 */
function localizarCartao(nome: string) {
  const botoes = within(obterListaLocais()).getAllByRole('button')
  const encontrado = botoes.find((botao) => within(botao).queryByText(nome) !== null)
  if (!encontrado) {
    throw new Error(`Nenhum cartao de local encontrado para "${nome}"`)
  }
  return encontrado
}

describe('Mapa', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  it('mostra os dez locais de Kanto', async () => {
    vi.stubGlobal('fetch', criarFetchMock({ mapa: respostaMapaExemplo() }))

    renderMapa()
    await screen.findByRole('heading', { name: 'Mapa de Kanto' })

    const listaLocais = obterListaLocais()
    for (const nome of [
      'Pallet Town',
      'Route 1',
      'Route 2',
      'Viridian City',
      'Pewter City',
      'Viridian Forest',
      'Route 3',
      'Mt. Moon',
      'Route 22',
      'Cerulean City',
    ]) {
      expect(within(listaLocais).getByText(nome)).toBeInTheDocument()
    }
    expect(within(listaLocais).getAllByRole('button')).toHaveLength(10)
  })

  it('mostra tambem o mapa interativo, com cada local reconhecivel por nome e estado', async () => {
    vi.stubGlobal('fetch', criarFetchMock({ mapa: respostaMapaExemplo() }))

    renderMapa()
    await screen.findByRole('heading', { name: 'Mapa de Kanto' })

    const mapa = screen.getByRole('group', { name: 'Mapa de Kanto' })
    expect(within(mapa).getByRole('button', { name: 'Pallet Town, visitado' })).toBeInTheDocument()
    expect(
      within(mapa).getByRole('button', { name: 'Route 1, alcancavel' }),
    ).toBeInTheDocument()
    expect(
      within(mapa).getByRole('button', { name: 'Pewter City, fora de alcance' }),
    ).toBeInTheDocument()
  })

  it('clicar num local no mapa destaca o mesmo local na lista, sem navegar', async () => {
    vi.stubGlobal('fetch', criarFetchMock({ mapa: respostaMapaExemplo() }))

    renderMapa()
    await screen.findByRole('heading', { name: 'Mapa de Kanto' })

    const mapa = screen.getByRole('group', { name: 'Mapa de Kanto' })
    fireEvent.click(within(mapa).getByRole('button', { name: 'Route 1, alcancavel' }))

    await waitFor(() => {
      expect(localizarCartao('Route 1')).toHaveAttribute('aria-pressed', 'true')
    })
    // Clicar no mapa so destaca na lista: continua na mesma tela.
    expect(screen.getByRole('heading', { name: 'Mapa de Kanto' })).toBeInTheDocument()
  })

  it('mostra o estado de cada local: visitado, alcancavel ou fora de alcance', async () => {
    vi.stubGlobal('fetch', criarFetchMock({ mapa: respostaMapaExemplo() }))

    renderMapa()

    await screen.findByRole('heading', { name: 'Mapa de Kanto' })

    expect(screen.getAllByText('Visitado')).toHaveLength(1)
    expect(screen.getAllByText('Alcancavel')).toHaveLength(1)
    expect(screen.getAllByText('Fora de alcance')).toHaveLength(8)
  })

  it('preserva a ordem que o servidor mandou, sem reordenar por conta propria', async () => {
    // A tela reordenava pela duracao estimada, que e viagem MAIS exploracao do
    // destino. O servidor ordena por custo de VIAGEM. Com metricas diferentes,
    // um local perto de muitos encontros aparecia depois de um longe de poucos,
    // e a tela contradizia a ordem que a API tinha escolhido. Decidir a ordem
    // no cliente e decidir no cliente, mesmo com dados prontos (Artigo II).
    const resposta = respostaMapaExemplo()
    const [palletTown, route1, ...resto] = resposta.items
    const ordemDoServidor = [...resto, route1, palletTown]

    vi.stubGlobal('fetch', criarFetchMock({ mapa: { ...resposta, items: ordemDoServidor } }))

    renderMapa()
    await screen.findByRole('heading', { name: 'Mapa de Kanto' })

    const botoes = within(obterListaLocais()).getAllByRole('button')
    expect(botoes).toHaveLength(ordemDoServidor.length)

    function indiceDoLocal(nome: string) {
      return botoes.findIndex((botao) => within(botao).queryByText(nome) !== null)
    }

    ordemDoServidor.forEach((local, posicao) => {
      expect(indiceDoLocal(local.nome)).toBe(posicao)
    })
  })

  it('local fora de alcance mostra o que falta visitar antes', async () => {
    vi.stubGlobal('fetch', criarFetchMock({ mapa: respostaMapaExemplo() }))

    renderMapa()
    await screen.findByRole('heading', { name: 'Mapa de Kanto' })

    const cartaoPewter = localizarCartao('Pewter City')
    expect(within(cartaoPewter).getByText('Visite Route 1 antes.')).toBeInTheDocument()
  })

  it('local sem avistamento mostra o vazio que convida, sem contagem de especies', async () => {
    vi.stubGlobal(
      'fetch',
      criarFetchMock({
        mapa: respostaMapaExemplo(),
        detalhePorId: {
          'route-1': localDetalhadoExemplo({
            id: 'route-1',
            nome: 'Route 1',
            especies_avistadas: [],
          }),
        },
      }),
    )

    renderMapa()
    await screen.findByRole('heading', { name: 'Mapa de Kanto' })

    fireEvent.click(localizarCartao('Route 1'))

    expect(
      await screen.findByText(
        'Nenhum Pokemon avistado aqui ainda. Mande um treinador para descobrir o que mora neste lugar.',
      ),
    ).toBeInTheDocument()

    const painelDeDetalhe = screen.getByRole('region', { name: 'Detalhe do local' })
    expect(within(painelDeDetalhe).queryByText(/\d+\s*(de|\/)\s*\d+/)).not.toBeInTheDocument()
  })

  it('local com avistamento lista as especies avistadas', async () => {
    vi.stubGlobal(
      'fetch',
      criarFetchMock({
        mapa: respostaMapaExemplo(),
        detalhePorId: {
          'pallet-town': localDetalhadoExemplo({
            id: 'pallet-town',
            nome: 'Pallet Town',
            especies_avistadas: [
              especieAvistadaExemplo({ especie_id: 16, nome: 'Pidgey', vezes_visto: 4 }),
            ],
          }),
        },
      }),
    )

    renderMapa()
    await screen.findByRole('heading', { name: 'Mapa de Kanto' })

    fireEvent.click(localizarCartao('Pallet Town'))

    expect(await screen.findByText('Pidgey')).toBeInTheDocument()
    expect(screen.getByText('Avistado 4 vezes')).toBeInTheDocument()
  })

  it('exibe mensagem de erro do servidor e permite tentar novamente', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        respostaJson(
          { erro: { codigo: 'ERRO_INTERNO', mensagem: 'Nao foi possivel carregar o mapa.' } },
          500,
        ),
      ),
    )

    renderMapa()

    expect(await screen.findByRole('alert')).toHaveTextContent('Nao foi possivel carregar o mapa.')
    expect(screen.getByRole('button', { name: /tentar novamente/i })).toBeInTheDocument()
  })
})
