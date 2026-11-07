import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  expedicaoResumoExemplo,
  itensExemplo,
  laboratorioExemplo,
  listaPokemonExemplo,
  perfilExemplo,
  pokemonDetalheExemplo,
  pokemonResumoExemplo,
  respostaExpedicoesExemplo,
  resumoExemplo,
} from '@/api/fixtures'
import { Laboratorio } from '@/pages/Laboratorio'
import { guardarSessao } from '@/store/auth'

function respostaJson(corpo: unknown, status = 200) {
  return { ok: status < 400, status, json: async () => corpo }
}

/**
 * Mock de fetch roteado por URL, porque a tela agora chama tres endpoints
 * (/me, /pokemon, /items) em paralelo: um unico mockResolvedValue devolveria
 * a mesma resposta para todos, como a Fase 2 ja ensinou a nao fazer.
 */
function criarFetchMock(
  manipulador: (url: string, init?: RequestInit) => ReturnType<typeof respostaJson>,
) {
  return vi.fn((entrada: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof entrada === 'string' ? entrada : entrada.toString()
    return Promise.resolve(manipulador(url, init))
  })
}

function manipuladorPadrao(url: string, init?: RequestInit) {
  if (init?.method === 'PATCH' && /\/pokemon\/[^/?]+$/.test(url)) {
    const corpo = JSON.parse(String(init.body)) as { apelido: string | null }
    return respostaJson(pokemonDetalheExemplo({ nome: corpo.apelido ?? 'Bulbasaur' }))
  }
  if (/\/pokemon\/[^/?]+$/.test(url)) {
    return respostaJson(pokemonDetalheExemplo())
  }
  if (url.includes('/pokemon?')) {
    return respostaJson(listaPokemonExemplo())
  }
  if (url.includes('/items')) {
    return respostaJson(itensExemplo())
  }
  if (url.includes('/expeditions')) {
    return respostaJson(respostaExpedicoesExemplo({ items: [], total: 0 }))
  }
  if (url.includes('/me')) {
    return respostaJson(perfilExemplo())
  }
  throw new Error(`URL nao mapeada no mock: ${url}`)
}

function renderLaboratorio() {
  return render(
    <MemoryRouter>
      <Laboratorio />
    </MemoryRouter>,
  )
}

describe('Laboratorio', () => {
  beforeEach(() => {
    window.localStorage.clear()
    guardarSessao({
      token: 'token-valido',
      professor: { id: '1', usuario: 'ash', nome_exibicao: 'Ash' },
      laboratorio: laboratorioExemplo(),
    })
  })

  it('mostra os dados do laboratorio vindos do /me', async () => {
    vi.stubGlobal(
      'fetch',
      criarFetchMock((url, init) => {
        if (url.includes('/me')) {
          return respostaJson(
            perfilExemplo({
              laboratorio: laboratorioExemplo({ nivel: 2, experiencia: 40, moedas: 120 }),
            }),
          )
        }
        return manipuladorPadrao(url, init)
      }),
    )

    renderLaboratorio()

    expect(await screen.findByRole('heading', { name: 'Lab Pallet' })).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText('120')).toBeInTheDocument()
    expect(screen.getByText('Professor Ash')).toBeInTheDocument()
    expect(screen.queryByText(/nenhum treinador/i)).not.toBeInTheDocument()
  })

  it('sem treinador no laboratorio orienta o professor a recrutar um', async () => {
    vi.stubGlobal(
      'fetch',
      criarFetchMock((url, init) => {
        if (url.includes('/me')) {
          return respostaJson(
            perfilExemplo({
              resumo: resumoExemplo({
                pokemon: 0,
                treinadores: 0,
                especies_vistas: 0,
                especies_capturadas: 0,
              }),
            }),
          )
        }
        return manipuladorPadrao(url, init)
      }),
    )

    renderLaboratorio()

    expect(
      await screen.findByText(
        'Nenhum treinador no laboratorio. Recrute um para comecar a despachar expedicoes.',
      ),
    ).toBeInTheDocument()
  })

  it('exibe mensagem de erro do servidor e permite tentar novamente', async () => {
    vi.stubGlobal(
      'fetch',
      criarFetchMock((url, init) => {
        if (url.includes('/me')) {
          return respostaJson(
            {
              erro: {
                codigo: 'ERRO_INTERNO',
                mensagem: 'Nao foi possivel carregar o laboratorio agora.',
              },
            },
            500,
          )
        }
        return manipuladorPadrao(url, init)
      }),
    )

    renderLaboratorio()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Nao foi possivel carregar o laboratorio agora.',
    )
    expect(screen.getByRole('button', { name: /tentar novamente/i })).toBeInTheDocument()
  })

  it('a lista mostra os cartoes dos Pokemon do acervo', async () => {
    vi.stubGlobal(
      'fetch',
      criarFetchMock((url, init) => {
        if (url.includes('/pokemon?')) {
          return respostaJson(
            listaPokemonExemplo({
              items: [
                pokemonResumoExemplo({ id: 'poke-1', nome: 'Bulbasaur' }),
                pokemonResumoExemplo({
                  id: 'poke-2',
                  nome: 'Fofo',
                  especie_id: 4,
                  especie_nome: 'Charmander',
                  tipo_primario: 'fire',
                  tipo_secundario: null,
                }),
              ],
              total: 2,
            }),
          )
        }
        return manipuladorPadrao(url, init)
      }),
    )

    renderLaboratorio()

    expect(await screen.findByRole('button', { name: /Bulbasaur/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Fofo/ })).toBeInTheDocument()
    expect(screen.getByText('1-2 de 2')).toBeInTheDocument()
  })

  it('o filtro de tipo chama a API com o parametro certo', async () => {
    const fetchMock = criarFetchMock(manipuladorPadrao)
    vi.stubGlobal('fetch', fetchMock)

    renderLaboratorio()

    await screen.findByRole('button', { name: /Bulbasaur/ })

    fireEvent.change(screen.getByLabelText('Tipo'), { target: { value: 'fire' } })

    await waitFor(() => {
      const chamadaComFiltro = fetchMock.mock.calls.find(([entrada]) =>
        String(entrada).includes('/pokemon?') && String(entrada).includes('tipo=fire'),
      )
      expect(chamadaComFiltro).toBeDefined()
    })
  })

  it('clicar num cartao abre a ficha do Pokemon selecionado', async () => {
    vi.stubGlobal('fetch', criarFetchMock(manipuladorPadrao))

    renderLaboratorio()

    const cartao = await screen.findByRole('button', { name: /Bulbasaur/ })
    fireEvent.click(cartao)

    const ficha = await screen.findByRole('complementary', { name: /Ficha de Bulbasaur/ })
    expect(within(ficha).getByRole('heading', { name: 'Bulbasaur' })).toBeInTheDocument()
  })

  it('salvar um apelido novo atualiza a ficha e a lista', async () => {
    vi.stubGlobal(
      'fetch',
      criarFetchMock((url, init) => {
        if (init?.method === 'PATCH' && /\/pokemon\/[^/?]+$/.test(url)) {
          return respostaJson(pokemonDetalheExemplo({ nome: 'Fofoletes' }))
        }
        return manipuladorPadrao(url, init)
      }),
    )

    renderLaboratorio()

    const cartao = await screen.findByRole('button', { name: /Bulbasaur/ })
    fireEvent.click(cartao)

    await screen.findByRole('complementary', { name: /Ficha de Bulbasaur/ })

    const campoApelido = screen.getByLabelText('Apelido')
    fireEvent.change(campoApelido, { target: { value: 'Fofoletes' } })
    fireEvent.click(screen.getByRole('button', { name: /salvar apelido/i }))

    expect(await screen.findByRole('heading', { name: 'Fofoletes' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Fofoletes/ })).toBeInTheDocument()
  })

  it('a secao de itens do laboratorio chama-se Estoque', async () => {
    vi.stubGlobal('fetch', criarFetchMock(manipuladorPadrao))

    renderLaboratorio()

    expect(await screen.findByRole('heading', { name: 'Estoque' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Estoque' })).toBeInTheDocument()
  })

  it('mostra as expedicoes em andamento reusando o cartao de expedicao', async () => {
    const ativa = expedicaoResumoExemplo({
      treinador_nome: 'Ash',
      local_destino_nome: 'Route 1',
      estado_observado: 'EM_CURSO',
      segundos_restantes: 90,
    })
    vi.stubGlobal(
      'fetch',
      criarFetchMock((url, init) => {
        if (url.includes('/expeditions')) {
          return respostaJson(respostaExpedicoesExemplo({ items: [ativa], total: 1 }))
        }
        return manipuladorPadrao(url, init)
      }),
    )

    renderLaboratorio()

    const painel = await screen.findByRole('region', { name: 'Expedicoes em andamento' })
    const cartao = await within(painel).findByRole('article', { name: /Ash/i })
    expect(within(cartao).getByText('Destino: Route 1')).toBeInTheDocument()
    // O numero exibido e o mesmo que o CartaoExpedicao ja formata a partir do
    // servidor (Artigo II): esta tela nao reimplementa contador algum.
    expect(within(cartao).getByText('01:30')).toBeInTheDocument()
  })

  it('sem expedicao em andamento, o painel aponta para o despacho', async () => {
    vi.stubGlobal('fetch', criarFetchMock(manipuladorPadrao))

    renderLaboratorio()

    const painel = await screen.findByRole('region', { name: 'Expedicoes em andamento' })
    expect(await within(painel).findByText(/Nenhuma expedicao em andamento/)).toBeInTheDocument()
    expect(within(painel).getByRole('link', { name: /despache um treinador/i })).toHaveAttribute(
      'href',
      '/expedicoes',
    )
  })
})
