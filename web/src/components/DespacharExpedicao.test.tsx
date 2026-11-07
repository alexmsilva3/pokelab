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

  it('o retrato e o time do treinador aparecem na escolha', async () => {
    const pokemon = pokemonResumoExemplo({
      id: 'poke-1',
      nome: 'Bulbasaur',
      nivel: 5,
      sprite: '1-front.png',
    })
    const treinador = treinadorResumoExemplo({
      id: 'treinador-1',
      nome: 'Ash',
      nivel: 2,
      time: [pokemon],
    })
    vi.stubGlobal('fetch', montarFetchMock({ treinadores: [treinador] }))

    renderizar(<DespacharExpedicao onDespachado={vi.fn()} />)

    const botaoAsh = await screen.findByRole('button', { name: 'Ash (Nv. 2)' })
    // O retrato continua desenhado dentro do botao, so que marcado
    // decorativo: so aparece pro leitor de tela pedindo explicitamente os
    // elementos ocultos (`hidden: true`), nunca na consulta normal.
    expect(
      within(botaoAsh).getByRole('img', { name: 'Retrato de Ash', hidden: true }),
    ).toBeInTheDocument()
    expect(within(botaoAsh).queryByRole('img', { name: 'Retrato de Ash' })).not.toBeInTheDocument()

    // O time nao mora mais dentro do botao: e uma lista propria, irma dele,
    // que o leitor de tela encontra com papel de lista de verdade.
    const timeDoAsh = screen.getByRole('list', { name: 'Time de Ash' })
    expect(within(timeDoAsh).getByRole('img', { name: 'Bulbasaur' })).toBeInTheDocument()
    expect(within(timeDoAsh).getByText('Nv. 5')).toBeInTheDocument()
    expect(within(botaoAsh).queryByText('Bulbasaur')).not.toBeInTheDocument()
  })

  it('o nome acessivel do botao de treinador traz nome e nivel, sem o time virar ruido', async () => {
    const bulbasaur = pokemonResumoExemplo({ id: 'poke-1', nome: 'Bulbasaur', nivel: 5 })
    const pidgey = pokemonResumoExemplo({
      id: 'poke-2',
      nome: 'Pidgey',
      especie_nome: 'Pidgey',
      nivel: 4,
    })
    const treinador = treinadorResumoExemplo({
      id: 'treinador-1',
      nome: 'Pat',
      nivel: 2,
      time: [bulbasaur, pidgey],
    })
    vi.stubGlobal('fetch', montarFetchMock({ treinadores: [treinador] }))

    renderizar(<DespacharExpedicao onDespachado={vi.fn()} />)

    // O nome acessivel e EXATAMENTE o texto visivel do botao. O WCAG 2.5.3
    // (Label in Name) exige isso: quem controla o navegador por voz fala o que
    // le na tela, e "clicar em Ash Nv 2" precisa casar com o nome computado.
    expect(await screen.findByRole('button', { name: 'Pat (Nv. 2)' })).toBeInTheDocument()

    // O time fica FORA do nome: ele ja e uma lista irma do botao, navegavel por
    // leitor de tela. Repetir ali daria a mesma informacao duas vezes e
    // transformaria o nome do botao numa frase longa.
    expect(screen.queryByRole('button', { name: /Bulbasaur/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Pidgey/ })).not.toBeInTheDocument()
    expect(screen.getByRole('list', { name: 'Time de Pat' })).toBeInTheDocument()
  })

  it('selecionar um destino no mapa preenche o campo de destino e mostra o escolhido', async () => {
    const treinador = treinadorResumoExemplo({ id: 'treinador-1', nome: 'Ash', time: [pokemonResumoExemplo()] })
    const local = localNoMapaExemplo({ id: 'route-1', nome: 'Route 1', estado: 'ALCANCAVEL' })
    vi.stubGlobal('fetch', montarFetchMock({ treinadores: [treinador], locais: [local] }))

    renderizar(<DespacharExpedicao onDespachado={vi.fn()} />)

    expect(await screen.findByText('Nenhum destino escolhido ainda.')).toBeInTheDocument()

    const mapa = screen.getByRole('group', { name: 'Mapa de Kanto' })
    fireEvent.click(within(mapa).getByRole('button', { name: 'Route 1, alcancavel' }))

    expect(await screen.findByText('Destino escolhido:')).toBeInTheDocument()
    expect(screen.getByText('Route 1', { selector: 'strong' })).toBeInTheDocument()
    // A lista de destinos (alternativa ao mapa) reflete a mesma escolha.
    expect(screen.getByRole('button', { name: 'Route 1' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('escolher o destino pela lista, sem usar o mapa, tambem preenche o destino', async () => {
    const treinador = treinadorResumoExemplo({ id: 'treinador-1', nome: 'Ash', time: [pokemonResumoExemplo()] })
    const local = localNoMapaExemplo({ id: 'route-1', nome: 'Route 1', estado: 'ALCANCAVEL' })
    vi.stubGlobal('fetch', montarFetchMock({ treinadores: [treinador], locais: [local] }))

    renderizar(<DespacharExpedicao onDespachado={vi.fn()} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Route 1' }))

    expect(await screen.findByText('Destino escolhido:')).toBeInTheDocument()
    expect(screen.getByText('Route 1', { selector: 'strong' })).toBeInTheDocument()
    // O mapa (alcancavel, agora selecionado) tambem reflete a mesma escolha.
    const mapa = screen.getByRole('group', { name: 'Mapa de Kanto' })
    expect(
      within(mapa).getByRole('button', { name: 'Route 1, alcancavel, selecionado' }),
    ).toBeInTheDocument()
  })

  it('a etapa da mochila usa o rotulo Mochila e diz o que cada item faz', async () => {
    const treinador = treinadorResumoExemplo({ id: 'treinador-1', nome: 'Ash' })
    const pokebola = itemEstoqueExemplo({ item_id: 'poke-ball', nome: 'Poke Ball', categoria: 'POKEBOLA' })
    const pocao = itemEstoqueExemplo({ item_id: 'potion', nome: 'Potion', categoria: 'CURA' })
    vi.stubGlobal(
      'fetch',
      montarFetchMock({ treinadores: [treinador], itens: [pokebola, pocao] }),
    )

    renderizar(<DespacharExpedicao onDespachado={vi.fn()} />)

    const etapaMochila = await screen.findByRole('group', { name: '3. Mochila' })
    expect(within(etapaMochila).getByText(/Captura um Pokemon selvagem/)).toBeInTheDocument()
    expect(within(etapaMochila).getByText(/Cura HP do time/)).toBeInTheDocument()
  })
})
