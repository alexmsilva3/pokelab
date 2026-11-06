import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { expedicaoLerExemplo, respostaTreinadoresExemplo } from '@/api/fixtures'
import type { ExpedicaoLer } from '@/api/tipos'
import { Expedicoes } from '@/pages/Expedicoes'

function respostaJson(corpo: unknown, status = 200) {
  return { ok: status < 400, status, json: async () => corpo }
}

function montarFetchMock(opcoes: { expedicoes: ExpedicaoLer[]; abortarResultado?: ExpedicaoLer }) {
  let itensAtuais = opcoes.expedicoes

  const fetchMock = vi.fn((url: unknown, init?: RequestInit) => {
    const caminho = String(url)

    if (init?.method === 'DELETE') {
      return Promise.resolve(
        respostaJson(opcoes.abortarResultado ?? expedicaoLerExemplo({ estado_observado: 'ABORTADA' })),
      )
    }
    if (caminho.includes('/expeditions')) {
      return Promise.resolve(respostaJson({ items: itensAtuais, total: itensAtuais.length }))
    }
    if (caminho.includes('/trainers')) {
      return Promise.resolve(respostaJson(respostaTreinadoresExemplo({ items: [] })))
    }
    if (caminho.includes('/items')) {
      return Promise.resolve(respostaJson({ items: [] }))
    }
    if (caminho.includes('/map')) {
      return Promise.resolve(respostaJson({ items: [], visitados: 0, total: 0 }))
    }
    throw new Error(`Chamada inesperada no mock de fetch: ${caminho}`)
  })

  return {
    fetchMock,
    definirItens(itens: ExpedicaoLer[]) {
      itensAtuais = itens
    },
  }
}

/**
 * Com o relogio falso ativo, nada que dependa de `setInterval`/`setTimeout`
 * reais (como o polling interno de `findBy*`/`waitFor`) avanca sozinho. O
 * fetch mockado resolve por microtarefas, entao bastam varias voltas da fila
 * de microtarefas — sem tocar no relogio — para a tela terminar de renderizar
 * o resultado de uma chamada ja resolvida.
 */
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
      <Expedicoes />
    </MemoryRouter>,
  )
}

describe('Expedicoes', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('lista vazia convida a despachar uma expedicao', async () => {
    const { fetchMock } = montarFetchMock({ expedicoes: [] })
    vi.stubGlobal('fetch', fetchMock)

    renderizar()
    await esvaziarMicrotarefas()

    expect(
      screen.getByText('Nenhuma expedicao em curso. Despache um treinador acima para comecar.'),
    ).toBeInTheDocument()
  })

  it('mostra as expedicoes ativas com treinador, destino e tempo restante do servidor', async () => {
    const ativa = expedicaoLerExemplo({
      id: 'expedicao-1',
      treinador_nome: 'Ash',
      local_destino_nome: 'Route 1',
      estado_observado: 'EM_CURSO',
      segundos_restantes: 90,
    })
    const { fetchMock } = montarFetchMock({ expedicoes: [ativa] })
    vi.stubGlobal('fetch', fetchMock)

    renderizar()
    await esvaziarMicrotarefas()

    const cartao = screen.getByRole('article', { name: /Ash/i })
    expect(within(cartao).getByText('Destino: Route 1')).toBeInTheDocument()
    expect(within(cartao).getByText('01:30')).toBeInTheDocument()
  })

  it('o contador decresce com o tempo falso dentro do painel de ativas', async () => {
    const ativa = expedicaoLerExemplo({ segundos_restantes: 10, estado_observado: 'EM_CURSO' })
    const { fetchMock } = montarFetchMock({ expedicoes: [ativa] })
    vi.stubGlobal('fetch', fetchMock)

    renderizar()
    await esvaziarMicrotarefas()
    expect(screen.getByText('00:10')).toBeInTheDocument()

    await act(async () => {
      vi.advanceTimersByTime(3000)
    })

    expect(screen.getByText('00:07')).toBeInTheDocument()
  })

  it('ao chegar a zero, consulta o servidor e mostra o estado_observado devolvido', async () => {
    const expedicaoEmCurso = expedicaoLerExemplo({
      id: 'expedicao-1',
      estado_observado: 'EM_CURSO',
      segundos_restantes: 2,
    })
    const expedicaoAguardando = expedicaoLerExemplo({
      id: 'expedicao-1',
      estado_observado: 'AGUARDANDO_RELATORIO',
      segundos_restantes: 0,
    })

    const { fetchMock, definirItens } = montarFetchMock({ expedicoes: [expedicaoEmCurso] })
    vi.stubGlobal('fetch', fetchMock)

    renderizar()
    await esvaziarMicrotarefas()
    expect(screen.getByText('00:02')).toBeInTheDocument()

    // O servidor passa a devolver o estado terminado assim que o contador
    // local chegar a zero e a tela consultar de novo — a tela nunca declara
    // isso sozinha a partir do proprio relogio.
    definirItens([expedicaoAguardando])

    await act(async () => {
      vi.advanceTimersByTime(2000)
    })
    await esvaziarMicrotarefas()

    expect(screen.getByText('Aguardando relatorio')).toBeInTheDocument()
  })

  it('abortar pede confirmacao e chama o DELETE da expedicao', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const ativa = expedicaoLerExemplo({ id: 'expedicao-1', estado_observado: 'EM_CURSO' })
    const { fetchMock, definirItens } = montarFetchMock({ expedicoes: [ativa] })
    vi.stubGlobal('fetch', fetchMock)

    renderizar()
    await esvaziarMicrotarefas()

    const botaoAbortar = screen.getByRole('button', { name: 'Abortar' })
    definirItens([])
    fireEvent.click(botaoAbortar)
    await esvaziarMicrotarefas()

    expect(confirmSpy).toHaveBeenCalled()
    expect(fetchMock.mock.calls.some((chamada) => chamada[1]?.method === 'DELETE')).toBe(true)

    confirmSpy.mockRestore()
  })
})
