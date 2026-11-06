import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  listaPokemonExemplo,
  pokemonResumoExemplo,
  previaTimeExemplo,
  treinadorDetalheExemplo,
} from '@/api/fixtures'
import type { ComposicaoTimeEntrada, PokemonResumo, PreviaTime, TreinadorDetalhe } from '@/api/tipos'
import { MontarTime } from '@/components/MontarTime'

function respostaJson(corpo: unknown, status = 200) {
  return { ok: status < 400, status, json: async () => corpo }
}

/**
 * Um unico mock de fetch que distingue as quatro chamadas da montagem pela
 * URL e pelo metodo, do mesmo jeito que o servidor real as distingue.
 */
function montarFetchMock(opcoes: {
  detalhe: TreinadorDetalhe
  livres?: PokemonResumo[]
  previa?: PreviaTime
  salvarComo?: TreinadorDetalhe
}) {
  return vi.fn((url: unknown, init?: RequestInit) => {
    const caminho = String(url)

    if (caminho.endsWith('/team/preview')) {
      return Promise.resolve(respostaJson(opcoes.previa ?? previaTimeExemplo()))
    }
    if (init?.method === 'PUT' && caminho.endsWith('/team')) {
      return Promise.resolve(respostaJson(opcoes.salvarComo ?? opcoes.detalhe))
    }
    if (caminho.includes('/pokemon?')) {
      const itens = opcoes.livres ?? []
      return Promise.resolve(
        respostaJson(listaPokemonExemplo({ items: itens, total: itens.length, page_size: 100 })),
      )
    }
    if (/\/trainers\/[^/]+$/.test(caminho)) {
      return Promise.resolve(respostaJson(opcoes.detalhe))
    }
    throw new Error(`Chamada inesperada no mock de fetch: ${caminho}`)
  })
}

function corposDe(fetchMock: ReturnType<typeof vi.fn>, sufixoUrl: string): ComposicaoTimeEntrada[] {
  return fetchMock.mock.calls
    .filter((chamada: unknown[]) => String(chamada[0]).endsWith(sufixoUrl))
    .map((chamada: unknown[]) => JSON.parse(String((chamada[1] as RequestInit | undefined)?.body)))
}

describe('MontarTime', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  it('clicar num Pokemon livre o move para o time na tela', async () => {
    const pikachu = pokemonResumoExemplo({ id: 'poke-pikachu', nome: 'Pikachu' })
    const detalhe = treinadorDetalheExemplo({ id: 'treinador-1', nome: 'Ash', time: [] })

    vi.stubGlobal('fetch', montarFetchMock({ detalhe, livres: [pikachu] }))

    render(<MontarTime treinadorId="treinador-1" />)

    expect(await screen.findByText('Time atual (0 / 3)')).toBeInTheDocument()
    const botaoPikachu = await screen.findByRole('button', { name: /Pikachu/i })
    expect(botaoPikachu).toHaveAttribute('aria-pressed', 'false')

    fireEvent.click(botaoPikachu)

    await waitFor(() => expect(screen.getByText('Time atual (1 / 3)')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /Pikachu/i })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('a previa e chamada a cada mudanca de composicao', async () => {
    const pikachu = pokemonResumoExemplo({ id: 'poke-pikachu', nome: 'Pikachu' })
    const charmander = pokemonResumoExemplo({ id: 'poke-charmander', nome: 'Charmander' })
    const detalhe = treinadorDetalheExemplo({ id: 'treinador-1', nome: 'Ash', time: [] })

    const fetchMock = montarFetchMock({ detalhe, livres: [pikachu, charmander] })
    vi.stubGlobal('fetch', fetchMock)

    render(<MontarTime treinadorId="treinador-1" />)

    await screen.findByText('Pikachu')
    await waitFor(() => {
      expect(corposDe(fetchMock, '/team/preview')).toHaveLength(1)
    })

    fireEvent.click(screen.getByRole('button', { name: /Pikachu/i }))
    await waitFor(() => {
      expect(corposDe(fetchMock, '/team/preview')).toHaveLength(2)
    })

    fireEvent.click(screen.getByRole('button', { name: /Charmander/i }))
    await waitFor(() => {
      expect(corposDe(fetchMock, '/team/preview')).toHaveLength(3)
    })

    const ultimoCorpo = corposDe(fetchMock, '/team/preview').at(-1)
    expect(ultimoCorpo?.pokemon_ids.sort()).toEqual(['poke-charmander', 'poke-pikachu'].sort())
  })

  it('o poder exibido vem da previa, nao e calculado no cliente', async () => {
    const detalhe = treinadorDetalheExemplo({
      id: 'treinador-1',
      nome: 'Ash',
      time: [],
      poder: 1,
    })
    // Valor deliberadamente estranho: se a tela calculasse poder sozinha a
    // partir do time (que esta vazio), nunca chegaria neste numero.
    const previa = previaTimeExemplo({ poder: 4242, capacidade_bagagem: 4 })

    vi.stubGlobal('fetch', montarFetchMock({ detalhe, livres: [], previa }))

    render(<MontarTime treinadorId="treinador-1" />)

    expect(await screen.findByText('4242')).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument()
  })

  it('composicao invalida mostra o motivo que o servidor mandou', async () => {
    const detalhe = treinadorDetalheExemplo({ id: 'treinador-1', nome: 'Ash', time: [] })
    const previa = previaTimeExemplo({
      valido: false,
      motivo: 'Este Pokemon ja esta com outro treinador.',
    })

    vi.stubGlobal('fetch', montarFetchMock({ detalhe, livres: [], previa }))

    render(<MontarTime treinadorId="treinador-1" />)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Este Pokemon ja esta com outro treinador.',
    )
    expect(screen.getByRole('button', { name: /salvar time/i })).toBeDisabled()
  })

  it('salvar chama o PUT com a lista completa de pokemon do time', async () => {
    const pikachu = pokemonResumoExemplo({ id: 'poke-pikachu', nome: 'Pikachu' })
    const detalhe = treinadorDetalheExemplo({ id: 'treinador-1', nome: 'Ash', time: [] })
    const detalheSalvo = treinadorDetalheExemplo({
      id: 'treinador-1',
      nome: 'Ash',
      time: [pikachu],
    })

    const fetchMock = montarFetchMock({
      detalhe,
      livres: [pikachu],
      previa: previaTimeExemplo({ valido: true }),
      salvarComo: detalheSalvo,
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<MontarTime treinadorId="treinador-1" />)

    fireEvent.click(await screen.findByRole('button', { name: /Pikachu/i }))
    await waitFor(() => expect(screen.getByText('Time atual (1 / 3)')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /salvar time/i }))

    await waitFor(() => {
      expect(corposDe(fetchMock, '/team')).toContainEqual({ pokemon_ids: ['poke-pikachu'] })
    })
  })

  it('treinador ocupado mostra o motivo e nao oferece como alterar o time', async () => {
    const pikachu = pokemonResumoExemplo({ id: 'poke-pikachu', nome: 'Pikachu' })
    const detalhe = treinadorDetalheExemplo({
      id: 'treinador-1',
      nome: 'Ash',
      status: 'EM_EXPEDICAO',
      time: [pikachu],
    })

    const fetchMock = montarFetchMock({ detalhe })
    vi.stubGlobal('fetch', fetchMock)

    render(<MontarTime treinadorId="treinador-1" />)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Treinador em expedicao: nao e possivel alterar o time agora.',
    )
    expect(screen.queryByRole('button', { name: /salvar time/i })).not.toBeInTheDocument()
    expect(corposDe(fetchMock, '/team/preview')).toHaveLength(0)
  })
})
