import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { pokemonResumoExemplo, viveiroExemplo } from '@/api/fixtures'
import { Viveiro } from '@/pages/Viveiro'

function respostaJson(corpo: unknown, status = 200) {
  return { ok: status < 400, status, json: async () => corpo }
}

async function esvaziarMicrotarefas() {
  for (let i = 0; i < 10; i += 1) {
    await act(async () => {
      await Promise.resolve()
    })
  }
}

function renderizar() {
  return render(
    <MemoryRouter>
      <Viveiro />
    </MemoryRouter>,
  )
}

describe('Viveiro', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('mostra ocupacao e capacidade do viveiro', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        respostaJson(viveiroExemplo({ ocupacao: 12, capacidade: 50, items: [] })),
      ),
    )

    renderizar()
    await esvaziarMicrotarefas()

    expect(screen.getByText('12 / 50')).toBeInTheDocument()
  })

  it('viveiro vazio orienta o professor sobre o que fazer', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(respostaJson(viveiroExemplo({ items: [] }))),
    )

    renderizar()
    await esvaziarMicrotarefas()

    expect(
      screen.getByText(/Nenhum Pokemon no viveiro agora/),
    ).toBeInTheDocument()
  })

  it('transbordado mostra quantos lugares faltam e as duas saidas (soltar ou entregar)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        respostaJson(
          viveiroExemplo({
            ocupacao: 52,
            capacidade: 50,
            transbordado: true,
            lugares_faltando: 2,
          }),
        ),
      ),
    )

    renderizar()
    await esvaziarMicrotarefas()

    const aviso = screen.getByRole('alert')
    expect(aviso).toHaveTextContent('faltam 2')
    expect(aviso).toHaveTextContent('Nenhuma expedicao nova pode partir')
    expect(screen.getByRole('link', { name: /entregue-os na Central de Entregas/ })).toHaveAttribute(
      'href',
      '/entregas',
    )
  })

  it('transbordado com um unico lugar faltando usa o singular', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        respostaJson(
          viveiroExemplo({
            ocupacao: 51,
            capacidade: 50,
            transbordado: true,
            lugares_faltando: 1,
          }),
        ),
      ),
    )

    renderizar()
    await esvaziarMicrotarefas()

    const aviso = screen.getByRole('alert')
    expect(aviso).toHaveTextContent('faltam 1 lugar.')
    expect(aviso).not.toHaveTextContent('lugares.')
  })

  it('sem transbordo, nenhum aviso aparece', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(respostaJson(viveiroExemplo({ transbordado: false }))),
    )

    renderizar()
    await esvaziarMicrotarefas()

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('soltar pede confirmacao nomeando o Pokemon e chama o DELETE ao confirmar', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const pokemon = pokemonResumoExemplo({ id: 'poke-1', nome: 'Pidgey', nivel: 4 })
    let itemRemovido = false
    const fetchMock = vi.fn((_url: unknown, init?: RequestInit) => {
      if (init?.method === 'DELETE') {
        itemRemovido = true
        return Promise.resolve(respostaJson(undefined, 204))
      }
      return Promise.resolve(
        respostaJson(viveiroExemplo({ items: itemRemovido ? [] : [pokemon] })),
      )
    })
    vi.stubGlobal('fetch', fetchMock)

    renderizar()
    await esvaziarMicrotarefas()

    fireEvent.click(screen.getByRole('button', { name: 'Soltar' }))

    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('Pidgey (Nv. 4)'))
    await esvaziarMicrotarefas()

    expect(fetchMock.mock.calls.some(([url, init]) => String(url).includes('poke-1') && init?.method === 'DELETE')).toBe(true)
    expect(screen.getByText(/Nenhum Pokemon no viveiro agora/)).toBeInTheDocument()

    confirmSpy.mockRestore()
  })

  it('cancelar a confirmacao nao chama o DELETE', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const pokemon = pokemonResumoExemplo({ id: 'poke-1', nome: 'Pidgey' })
    const fetchMock = vi.fn().mockResolvedValue(respostaJson(viveiroExemplo({ items: [pokemon] })))
    vi.stubGlobal('fetch', fetchMock)

    renderizar()
    await esvaziarMicrotarefas()

    fireEvent.click(screen.getByRole('button', { name: 'Soltar' }))
    await esvaziarMicrotarefas()

    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false)

    confirmSpy.mockRestore()
  })

  it('recusa do servidor ao soltar mostra a mensagem dele', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const pokemon = pokemonResumoExemplo({ id: 'poke-1', nome: 'Pidgey' })
    const fetchMock = vi.fn((_url: unknown, init?: RequestInit) => {
      if (init?.method === 'DELETE') {
        return Promise.resolve(
          respostaJson(
            { erro: { codigo: 'ULTIMO_POKEMON', mensagem: 'O laboratorio nao pode ficar sem nenhum Pokemon.' } },
            409,
          ),
        )
      }
      return Promise.resolve(respostaJson(viveiroExemplo({ items: [pokemon] })))
    })
    vi.stubGlobal('fetch', fetchMock)

    renderizar()
    await esvaziarMicrotarefas()

    fireEvent.click(screen.getByRole('button', { name: 'Soltar' }))
    await esvaziarMicrotarefas()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'O laboratorio nao pode ficar sem nenhum Pokemon.',
    )
  })
})
