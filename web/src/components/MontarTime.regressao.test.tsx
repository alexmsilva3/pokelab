import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  listaPokemonExemplo,
  pokemonResumoExemplo,
  previaTimeExemplo,
  treinadorDetalheExemplo,
} from '@/api/fixtures'
import { MontarTime } from '@/components/MontarTime'

function respostaJson(corpo: unknown, status = 200) {
  return { ok: status < 400, status, json: async () => corpo }
}

function fetchMock(detalhe: ReturnType<typeof treinadorDetalheExemplo>, livres: unknown[] = []) {
  return vi.fn().mockImplementation((url: string) => {
    const caminho = String(url)
    if (caminho.includes('/team/preview')) {
      return Promise.resolve(respostaJson(previaTimeExemplo()))
    }
    if (caminho.includes('/pokemon')) {
      return Promise.resolve(
        respostaJson(listaPokemonExemplo({ items: livres as never[], total: livres.length })),
      )
    }
    return Promise.resolve(respostaJson(detalhe))
  })
}

describe('MontarTime — regressao da revisao da Fase 4', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  it('Pokemon retirado do time volta para a coluna de disponiveis', async () => {
    // O defeito: a coluna de disponiveis vinha so de GET /pokemon?livre=true,
    // que por definicao nao traz quem ja tem treinador. Ao tirar um Pokemon do
    // time, ele sumia das duas colunas e nao havia como devolve-lo sem fechar
    // e reabrir o painel.
    const bulbasaur = pokemonResumoExemplo({ id: 'poke-bulba', nome: 'Bulbasaur' })
    const detalhe = treinadorDetalheExemplo({ id: 'treinador-1', time: [bulbasaur] })

    vi.stubGlobal('fetch', fetchMock(detalhe, []))
    render(<MontarTime treinadorId="treinador-1" />)

    const noTime = await screen.findByRole('button', { name: /Bulbasaur/i })
    fireEvent.click(noTime)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Bulbasaur/i })).toBeInTheDocument()
    })
  })

  it('com o laboratorio sem nenhum livre, o retirado ainda pode voltar', async () => {
    // O caso mais apertado: laboratorio novo, os tres iniciais todos no time.
    const time = [
      pokemonResumoExemplo({ id: 'p1', nome: 'Bulbasaur' }),
      pokemonResumoExemplo({ id: 'p2', nome: 'Charmander' }),
      pokemonResumoExemplo({ id: 'p3', nome: 'Squirtle' }),
    ]
    const detalhe = treinadorDetalheExemplo({ id: 'treinador-1', time })

    vi.stubGlobal('fetch', fetchMock(detalhe, []))
    render(<MontarTime treinadorId="treinador-1" />)

    fireEvent.click(await screen.findByRole('button', { name: /Charmander/i }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Charmander/i })).toBeInTheDocument()
    })
  })

  it('avisa o pai quando ha alteracoes nao salvas', async () => {
    // O aviso vive no pai porque o painel e remontado por key a cada troca de
    // treinador: o confirm interno do botao Fechar nunca rodava nesse caminho.
    const livre = pokemonResumoExemplo({ id: 'poke-livre', nome: 'Pikachu' })
    const detalhe = treinadorDetalheExemplo({ id: 'treinador-1', time: [] })
    const onPendenciasMudaram = vi.fn()

    vi.stubGlobal('fetch', fetchMock(detalhe, [livre]))
    render(
      <MontarTime treinadorId="treinador-1" onPendenciasMudaram={onPendenciasMudaram} />,
    )

    fireEvent.click(await screen.findByRole('button', { name: /Pikachu/i }))

    await waitFor(() => {
      expect(onPendenciasMudaram).toHaveBeenCalledWith(true)
    })
  })

  it('o tamanho maximo do time vem do servidor, nao de um literal', async () => {
    const detalhe = treinadorDetalheExemplo({ id: 'treinador-1', tamanho_maximo_time: 4 })

    vi.stubGlobal('fetch', fetchMock(detalhe, []))
    render(<MontarTime treinadorId="treinador-1" />)

    expect(await screen.findByText(/Time atual \(0 \/ 4\)/)).toBeInTheDocument()
  })

  it('treinador ocupado usa o campo do servidor, nao deduz do status', async () => {
    // statusOcupado reimplementava o invariante 3 no cliente (Artigo II).
    // Um status desconhecido pelo cliente mas marcado como ocupado pelo
    // servidor tem que travar a edicao do mesmo jeito.
    const detalhe = treinadorDetalheExemplo({ id: 'treinador-1', ocupado: true })

    vi.stubGlobal('fetch', fetchMock(detalhe, []))
    render(<MontarTime treinadorId="treinador-1" />)

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /salvar time/i })).not.toBeInTheDocument()
  })
})
