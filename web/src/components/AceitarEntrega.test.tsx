import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  entregaLerExemplo,
  listaPokemonExemplo,
  pokemonResumoExemplo,
  respostaTreinadoresExemplo,
  treinadorResumoExemplo,
} from '@/api/fixtures'
import type { EntregaLer, PokemonResumo, TreinadorResumo } from '@/api/tipos'
import { AceitarEntrega } from '@/components/AceitarEntrega'

function respostaJson(corpo: unknown, status = 200) {
  return { ok: status < 400, status, json: async () => corpo }
}

function montarFetchMock(opcoes: {
  livres: PokemonResumo[]
  treinadores: TreinadorResumo[]
  aceiteResultado?: EntregaLer
  aceiteStatus?: number
  aceiteDemorado?: boolean
}) {
  return vi.fn((url: unknown, init?: RequestInit) => {
    const caminho = String(url)

    if (init?.method === 'POST' && caminho.endsWith('/accept')) {
      if (opcoes.aceiteDemorado) return new Promise(() => {})
      return Promise.resolve(
        respostaJson(
          opcoes.aceiteResultado ?? entregaLerExemplo({ estado_observado: 'EM_CURSO' }),
          opcoes.aceiteStatus,
        ),
      )
    }
    if (caminho.includes('/pokemon?')) {
      return Promise.resolve(
        respostaJson(listaPokemonExemplo({ items: opcoes.livres, total: opcoes.livres.length })),
      )
    }
    if (caminho.includes('/trainers')) {
      return Promise.resolve(respostaJson(respostaTreinadoresExemplo({ items: opcoes.treinadores })))
    }
    throw new Error(`Chamada inesperada no mock de fetch: ${caminho}`)
  })
}

const pedidoDoisPidgey: EntregaLer = entregaLerExemplo({
  id: 'entrega-1',
  local_destino_nome: 'Cerulean City',
  requisitos: [
    { especie_id: 16, especie_nome: 'Pidgey', quantidade: 2, disponiveis_no_viveiro: 4 },
  ],
})

const quatroPidgey = [
  pokemonResumoExemplo({ id: 'pidgey-1', nome: 'Pidgey', especie_id: 16, nivel: 3 }),
  pokemonResumoExemplo({ id: 'pidgey-2', nome: 'Pidgey', especie_id: 16, nivel: 5 }),
  pokemonResumoExemplo({ id: 'pidgey-3', nome: 'Pidgey', especie_id: 16, nivel: 7 }),
  pokemonResumoExemplo({ id: 'pidgey-4', nome: 'Pidgey', especie_id: 16, nivel: 9 }),
]

const treinadorDisponivel = treinadorResumoExemplo({ id: 'treinador-1', nome: 'Ash', status: 'DISPONIVEL' })

describe('AceitarEntrega', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  it('mostra o nivel de cada candidato', async () => {
    vi.stubGlobal(
      'fetch',
      montarFetchMock({ livres: quatroPidgey, treinadores: [treinadorDisponivel] }),
    )

    render(
      <AceitarEntrega entrega={pedidoDoisPidgey} onAceito={vi.fn()} onCancelar={vi.fn()} />,
    )

    expect(await screen.findByRole('button', { name: 'Pidgey (Nv. 3)' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Pidgey (Nv. 5)' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Pidgey (Nv. 7)' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Pidgey (Nv. 9)' })).toBeInTheDocument()
  })

  it('exige selecionar exatamente a quantidade pedida antes de habilitar a confirmacao', async () => {
    vi.stubGlobal(
      'fetch',
      montarFetchMock({ livres: quatroPidgey, treinadores: [treinadorDisponivel] }),
    )

    render(
      <AceitarEntrega entrega={pedidoDoisPidgey} onAceito={vi.fn()} onCancelar={vi.fn()} />,
    )

    const confirmar = await screen.findByRole('button', { name: 'Confirmar aceite' })
    expect(confirmar).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: 'Pidgey (Nv. 3)' }))
    expect(confirmar).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: /Ash/ }))
    expect(confirmar).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: 'Pidgey (Nv. 5)' }))
    expect(confirmar).not.toBeDisabled()
  })

  it('nao permite selecionar mais do que a quantidade pedida', async () => {
    vi.stubGlobal(
      'fetch',
      montarFetchMock({ livres: quatroPidgey, treinadores: [treinadorDisponivel] }),
    )

    render(
      <AceitarEntrega entrega={pedidoDoisPidgey} onAceito={vi.fn()} onCancelar={vi.fn()} />,
    )

    await screen.findByRole('button', { name: 'Pidgey (Nv. 3)' })
    fireEvent.click(screen.getByRole('button', { name: 'Pidgey (Nv. 3)' }))
    fireEvent.click(screen.getByRole('button', { name: 'Pidgey (Nv. 5)' }))

    expect(screen.getByRole('button', { name: 'Pidgey (Nv. 7)' })).toBeDisabled()

    // Desmarcar um libera a escolha de outro.
    fireEvent.click(screen.getByRole('button', { name: 'Pidgey (Nv. 3)' }))
    expect(screen.getByRole('button', { name: 'Pidgey (Nv. 7)' })).not.toBeDisabled()
  })

  it('a confirmacao nomeia os Pokemon escolhidos antes de aceitar', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const onAceito = vi.fn()
    vi.stubGlobal(
      'fetch',
      montarFetchMock({ livres: quatroPidgey, treinadores: [treinadorDisponivel] }),
    )

    render(
      <AceitarEntrega entrega={pedidoDoisPidgey} onAceito={onAceito} onCancelar={vi.fn()} />,
    )

    fireEvent.click(await screen.findByRole('button', { name: 'Pidgey (Nv. 3)' }))
    fireEvent.click(screen.getByRole('button', { name: 'Pidgey (Nv. 5)' }))
    fireEvent.click(screen.getByRole('button', { name: /Ash/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar aceite' }))

    expect(confirmSpy).toHaveBeenCalledWith(
      expect.stringContaining('Pidgey (Nv. 3), Pidgey (Nv. 5)'),
    )

    await waitFor(() => expect(onAceito).toHaveBeenCalled())

    confirmSpy.mockRestore()
  })

  it('cancelar a confirmacao nao chama a API de aceite', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const fetchMock = montarFetchMock({ livres: quatroPidgey, treinadores: [treinadorDisponivel] })
    vi.stubGlobal('fetch', fetchMock)

    render(
      <AceitarEntrega entrega={pedidoDoisPidgey} onAceito={vi.fn()} onCancelar={vi.fn()} />,
    )

    fireEvent.click(await screen.findByRole('button', { name: 'Pidgey (Nv. 3)' }))
    fireEvent.click(screen.getByRole('button', { name: 'Pidgey (Nv. 5)' }))
    fireEvent.click(screen.getByRole('button', { name: /Ash/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar aceite' }))

    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/accept'))).toBe(false)

    confirmSpy.mockRestore()
  })

  it('desabilita o botao de confirmar enquanto a chamada de aceite esta em curso', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.stubGlobal(
      'fetch',
      montarFetchMock({
        livres: quatroPidgey,
        treinadores: [treinadorDisponivel],
        aceiteDemorado: true,
      }),
    )

    render(
      <AceitarEntrega entrega={pedidoDoisPidgey} onAceito={vi.fn()} onCancelar={vi.fn()} />,
    )

    fireEvent.click(await screen.findByRole('button', { name: 'Pidgey (Nv. 3)' }))
    fireEvent.click(screen.getByRole('button', { name: 'Pidgey (Nv. 5)' }))
    fireEvent.click(screen.getByRole('button', { name: /Ash/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar aceite' }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Enviando...' })).toBeDisabled(),
    )
  })

  it('recusa do servidor mostra a mensagem dele', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.stubGlobal(
      'fetch',
      montarFetchMock({
        livres: quatroPidgey,
        treinadores: [treinadorDisponivel],
        aceiteResultado: {
          erro: { codigo: 'TREINADOR_OCUPADO', mensagem: 'Este treinador ja esta ocupado.' },
        } as unknown as EntregaLer,
        aceiteStatus: 409,
      }),
    )

    render(
      <AceitarEntrega entrega={pedidoDoisPidgey} onAceito={vi.fn()} onCancelar={vi.fn()} />,
    )

    fireEvent.click(await screen.findByRole('button', { name: 'Pidgey (Nv. 3)' }))
    fireEvent.click(screen.getByRole('button', { name: 'Pidgey (Nv. 5)' }))
    fireEvent.click(screen.getByRole('button', { name: /Ash/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar aceite' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Este treinador ja esta ocupado.')
  })

  it('sem nenhum candidato da especie no viveiro, explica e nao permite confirmar', async () => {
    vi.stubGlobal(
      'fetch',
      montarFetchMock({ livres: [], treinadores: [treinadorDisponivel] }),
    )

    render(
      <AceitarEntrega entrega={pedidoDoisPidgey} onAceito={vi.fn()} onCancelar={vi.fn()} />,
    )

    expect(
      await screen.findByText('Nenhum Pidgey livre no viveiro para escolher.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirmar aceite' })).toBeDisabled()
  })

  it('sem treinador disponivel, explica e nao permite confirmar', async () => {
    vi.stubGlobal('fetch', montarFetchMock({ livres: quatroPidgey, treinadores: [] }))

    render(
      <AceitarEntrega entrega={pedidoDoisPidgey} onAceito={vi.fn()} onCancelar={vi.fn()} />,
    )

    expect(
      await screen.findByText(/Nenhum treinador disponivel/),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirmar aceite' })).toBeDisabled()
  })

  it('cancelar chama onCancelar', async () => {
    const onCancelar = vi.fn()
    vi.stubGlobal(
      'fetch',
      montarFetchMock({ livres: quatroPidgey, treinadores: [treinadorDisponivel] }),
    )

    render(
      <AceitarEntrega entrega={pedidoDoisPidgey} onAceito={vi.fn()} onCancelar={onCancelar} />,
    )

    fireEvent.click(await screen.findByRole('button', { name: 'Cancelar' }))

    expect(onCancelar).toHaveBeenCalled()
  })
})
