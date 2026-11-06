import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  expedicaoLerExemplo,
  itemEstoqueExemplo,
  localNoMapaExemplo,
  pokemonResumoExemplo,
  previaExpedicaoExemplo,
  respostaMapaExemplo,
  respostaTreinadoresExemplo,
  treinadorResumoExemplo,
} from '@/api/fixtures'
import type {
  ExpedicaoEntrada,
  ItemEmEstoque,
  LocalNoMapa,
  PreviaExpedicao,
  RespostaTreinadores,
  TreinadorResumo,
} from '@/api/tipos'
import { DespacharExpedicao } from '@/components/DespacharExpedicao'

function respostaJson(corpo: unknown, status = 200) {
  return { ok: status < 400, status, json: async () => corpo }
}

function montarFetchMock(opcoes: {
  treinadores?: TreinadorResumo[]
  locais?: LocalNoMapa[]
  itens?: ItemEmEstoque[]
  previa?: PreviaExpedicao
  despachoResultado?: unknown
}) {
  const treinadores: RespostaTreinadores = {
    items: opcoes.treinadores ?? respostaTreinadoresExemplo().items,
  }

  return vi.fn((url: unknown, init?: RequestInit) => {
    const caminho = String(url)

    if (caminho.endsWith('/expeditions/preview')) {
      return Promise.resolve(respostaJson(opcoes.previa ?? previaExpedicaoExemplo()))
    }
    if (init?.method === 'POST' && caminho.endsWith('/expeditions')) {
      return Promise.resolve(respostaJson(opcoes.despachoResultado ?? expedicaoLerExemplo()))
    }
    if (caminho.includes('/trainers')) {
      return Promise.resolve(respostaJson(treinadores))
    }
    if (caminho.includes('/items')) {
      return Promise.resolve(respostaJson({ items: opcoes.itens ?? [] }))
    }
    if (caminho.includes('/map')) {
      return Promise.resolve(
        respostaJson({
          items: opcoes.locais ?? respostaMapaExemplo().items,
          visitados: 1,
          total: (opcoes.locais ?? respostaMapaExemplo().items).length,
        }),
      )
    }
    throw new Error(`Chamada inesperada no mock de fetch: ${caminho}`)
  })
}

function corposDe(fetchMock: ReturnType<typeof vi.fn>, sufixoUrl: string): ExpedicaoEntrada[] {
  return fetchMock.mock.calls
    .filter((chamada: unknown[]) => String(chamada[0]).endsWith(sufixoUrl))
    .map((chamada: unknown[]) => JSON.parse(String((chamada[1] as RequestInit | undefined)?.body)))
}

function renderizar(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe('DespacharExpedicao', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  it('treinador sem time aparece indisponivel, com o motivo e um atalho para montar o time', async () => {
    const semTime = treinadorResumoExemplo({ id: 'treinador-vazio', nome: 'Misty', time: [] })
    vi.stubGlobal('fetch', montarFetchMock({ treinadores: [semTime] }))

    renderizar(<DespacharExpedicao onDespachado={vi.fn()} />)

    const listaTreinadores = await screen.findByRole('list', { name: 'Escolher treinador' })
    expect(within(listaTreinadores).getByText('Indisponivel')).toBeInTheDocument()
    expect(within(listaTreinadores).getByText(/Sem Pokemon no time\./)).toBeInTheDocument()
    expect(within(listaTreinadores).getByRole('link', { name: 'Montar o time' })).toHaveAttribute(
      'href',
      '/treinadores',
    )

    const botaoMisty = within(listaTreinadores).getByRole('button', { name: /Misty/i })
    expect(botaoMisty).toBeDisabled()
  })

  it('destino fora de alcance aparece indisponivel, com atalho para o mapa', async () => {
    const destinoFechado = localNoMapaExemplo({
      id: 'pewter-city',
      nome: 'Pewter City',
      estado: 'FORA_DE_ALCANCE',
      origem_id: null,
      origem_nome: null,
      duracao_estimada_minutos: null,
      proximo_passo_id: 'route-1',
      proximo_passo_nome: 'Route 1',
    })
    vi.stubGlobal('fetch', montarFetchMock({ locais: [destinoFechado] }))

    renderizar(<DespacharExpedicao onDespachado={vi.fn()} />)

    expect(await screen.findByText(/visite Route 1 antes/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ver mapa' })).toHaveAttribute('href', '/mapa')
    expect(screen.getByRole('button', { name: 'Pewter City' })).toBeDisabled()
  })

  it('a previa e chamada a cada mudanca de treinador, destino ou carga', async () => {
    const treinador = treinadorResumoExemplo({ id: 'treinador-1', nome: 'Ash', time: [pokemonResumoExemplo()] })
    const local = localNoMapaExemplo({ id: 'route-1', nome: 'Route 1', estado: 'ALCANCAVEL' })
    const item = itemEstoqueExemplo({ item_id: 'potion', nome: 'Potion', quantidade: 3 })

    const fetchMock = montarFetchMock({ treinadores: [treinador], locais: [local], itens: [item] })
    vi.stubGlobal('fetch', fetchMock)

    renderizar(<DespacharExpedicao onDespachado={vi.fn()} />)

    await screen.findByRole('button', { name: /Ash/i })
    expect(corposDe(fetchMock, '/expeditions/preview')).toHaveLength(0)

    fireEvent.click(screen.getByRole('button', { name: /Ash/i }))
    await waitFor(() => expect(corposDe(fetchMock, '/expeditions/preview')).toHaveLength(0))

    fireEvent.click(screen.getByRole('button', { name: 'Route 1' }))
    await waitFor(() => expect(corposDe(fetchMock, '/expeditions/preview')).toHaveLength(1))

    fireEvent.change(screen.getByLabelText(/Potion/), { target: { value: '2' } })
    await waitFor(() => expect(corposDe(fetchMock, '/expeditions/preview')).toHaveLength(2))

    const ultimoCorpo = corposDe(fetchMock, '/expeditions/preview').at(-1)
    expect(ultimoCorpo).toEqual({
      treinador_id: 'treinador-1',
      local_id: 'route-1',
      carga: [{ item_id: 'potion', quantidade: 2 }],
    })
  })

  it('previa recusada mostra o motivo que o servidor mandou, sem reescrever', async () => {
    const treinador = treinadorResumoExemplo({ id: 'treinador-1', nome: 'Ash', time: [pokemonResumoExemplo()] })
    const local = localNoMapaExemplo({ id: 'route-1', nome: 'Route 1', estado: 'ALCANCAVEL' })
    const previaRecusada = previaExpedicaoExemplo({
      valido: false,
      codigo: 'ESTOQUE_INSUFICIENTE',
      motivo: 'Nao ha Potion suficiente no estoque.',
    })

    vi.stubGlobal(
      'fetch',
      montarFetchMock({ treinadores: [treinador], locais: [local], previa: previaRecusada }),
    )

    renderizar(<DespacharExpedicao onDespachado={vi.fn()} />)

    fireEvent.click(await screen.findByRole('button', { name: /Ash/i }))
    fireEvent.click(screen.getByRole('button', { name: 'Route 1' }))

    expect(await screen.findByText('Nao ha Potion suficiente no estoque.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Despachar/i })).toBeDisabled()
  })

  it('despachar chama o POST com treinador, destino e carga escolhidos', async () => {
    const treinador = treinadorResumoExemplo({ id: 'treinador-1', nome: 'Ash', time: [pokemonResumoExemplo()] })
    const local = localNoMapaExemplo({ id: 'route-1', nome: 'Route 1', estado: 'ALCANCAVEL' })
    const onDespachado = vi.fn()

    const fetchMock = montarFetchMock({ treinadores: [treinador], locais: [local] })
    vi.stubGlobal('fetch', fetchMock)

    renderizar(<DespacharExpedicao onDespachado={onDespachado} />)

    fireEvent.click(await screen.findByRole('button', { name: /Ash/i }))
    fireEvent.click(screen.getByRole('button', { name: 'Route 1' }))

    const botaoDespachar = await screen.findByRole('button', { name: 'Despachar' })
    await waitFor(() => expect(botaoDespachar).toBeEnabled())

    fireEvent.click(botaoDespachar)

    await waitFor(() => expect(corposDe(fetchMock, '/expeditions')).toHaveLength(1))
    expect(corposDe(fetchMock, '/expeditions')[0]).toEqual({
      treinador_id: 'treinador-1',
      local_id: 'route-1',
      carga: [],
    })
    await waitFor(() => expect(onDespachado).toHaveBeenCalledTimes(1))
  })
})
