import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { expedicaoLerExemplo, respostaTreinadoresExemplo } from '@/api/fixtures'
import type { ExpedicaoLer } from '@/api/tipos'
import { Expedicoes } from '@/pages/Expedicoes'

function respostaJson(corpo: unknown, status = 200) {
  return { ok: status < 400, status, json: async () => corpo }
}

/**
 * A tela pede dois recortes de `GET /expeditions` (Expedicoes.tsx): ativas
 * (`...AGUARDANDO_RELATORIO`, exclusivo desse recorte) e historico (os tres
 * estados terminais). O mock devolve uma lista ou outra olhando a query —
 * do mesmo jeito que o servidor real filtra por `estado_observado`.
 */
function montarFetchMock(opcoes: {
  ativas: ExpedicaoLer[]
  historico?: ExpedicaoLer[]
  abortarResultado?: ExpedicaoLer
}) {
  let ativasAtuais = opcoes.ativas
  let historicoAtual = opcoes.historico ?? []

  const fetchMock = vi.fn((url: unknown, init?: RequestInit) => {
    const caminho = String(url)

    if (init?.method === 'DELETE') {
      return Promise.resolve(
        respostaJson(opcoes.abortarResultado ?? expedicaoLerExemplo({ estado_observado: 'ABORTADA' })),
      )
    }
    if (caminho.includes('/expeditions')) {
      const itens = caminho.includes('AGUARDANDO_RELATORIO') ? ativasAtuais : historicoAtual
      return Promise.resolve(respostaJson({ items: itens, total: itens.length }))
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
    definirAtivas(itens: ExpedicaoLer[]) {
      ativasAtuais = itens
    },
    definirHistorico(itens: ExpedicaoLer[]) {
      historicoAtual = itens
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

/** Com a rota de destino montada, para testar o clique em "Ver relatorio" do historico. */
function renderizarComRotaDeRelatorio() {
  return render(
    <MemoryRouter initialEntries={['/expedicoes']}>
      <Routes>
        <Route path="/expedicoes" element={<Expedicoes />} />
        <Route
          path="/expedicoes/:id/relatorio"
          element={<p>Tela do relatorio aberta</p>}
        />
      </Routes>
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
    const { fetchMock } = montarFetchMock({ ativas: [] })
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
    const { fetchMock } = montarFetchMock({ ativas: [ativa] })
    vi.stubGlobal('fetch', fetchMock)

    renderizar()
    await esvaziarMicrotarefas()

    const cartao = screen.getByRole('article', { name: /Ash/i })
    expect(within(cartao).getByText('Destino: Route 1')).toBeInTheDocument()
    expect(within(cartao).getByText('01:30')).toBeInTheDocument()
  })

  it('o contador decresce com o tempo falso dentro do painel de ativas', async () => {
    const ativa = expedicaoLerExemplo({ segundos_restantes: 10, estado_observado: 'EM_CURSO' })
    const { fetchMock } = montarFetchMock({ ativas: [ativa] })
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

    const { fetchMock, definirAtivas } = montarFetchMock({ ativas: [expedicaoEmCurso] })
    vi.stubGlobal('fetch', fetchMock)

    renderizar()
    await esvaziarMicrotarefas()
    expect(screen.getByText('00:02')).toBeInTheDocument()

    // O servidor passa a devolver o estado terminado assim que o contador
    // local chegar a zero e a tela consultar de novo — a tela nunca declara
    // isso sozinha a partir do proprio relogio.
    definirAtivas([expedicaoAguardando])

    await act(async () => {
      vi.advanceTimersByTime(2000)
    })
    await esvaziarMicrotarefas()

    expect(screen.getByText('Aguardando relatorio')).toBeInTheDocument()
  })

  it('abortar pede confirmacao e chama o DELETE da expedicao', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const ativa = expedicaoLerExemplo({ id: 'expedicao-1', estado_observado: 'EM_CURSO' })
    const { fetchMock, definirAtivas } = montarFetchMock({ ativas: [ativa] })
    vi.stubGlobal('fetch', fetchMock)

    renderizar()
    await esvaziarMicrotarefas()

    const botaoAbortar = screen.getByRole('button', { name: 'Abortar' })
    definirAtivas([])
    fireEvent.click(botaoAbortar)
    await esvaziarMicrotarefas()

    expect(confirmSpy).toHaveBeenCalled()
    expect(fetchMock.mock.calls.some((chamada) => chamada[1]?.method === 'DELETE')).toBe(true)

    confirmSpy.mockRestore()
  })

  it('historico vazio orienta o professor', async () => {
    const { fetchMock } = montarFetchMock({ ativas: [] })
    vi.stubGlobal('fetch', fetchMock)

    renderizar()
    await esvaziarMicrotarefas()

    expect(
      screen.getByText('Nenhuma expedicao concluida ainda. O historico aparece aqui assim que a primeira terminar.'),
    ).toBeInTheDocument()
  })

  it('uma expedicao concluida continua visivel no historico, com caminho de volta ao relatorio', async () => {
    const concluida = expedicaoLerExemplo({
      id: 'expedicao-9',
      treinador_nome: 'Misty',
      local_destino_nome: 'Cerulean Cave',
      status: 'CONCLUIDA_SUCESSO',
      estado_observado: 'CONCLUIDA_SUCESSO',
      segundos_restantes: null,
    })
    const { fetchMock } = montarFetchMock({ ativas: [], historico: [concluida] })
    vi.stubGlobal('fetch', fetchMock)

    renderizarComRotaDeRelatorio()
    await esvaziarMicrotarefas()

    const secaoHistorico = screen.getByRole('region', { name: 'Historico de expedicoes' })
    const cartao = within(secaoHistorico).getByRole('article', { name: /Misty/i })
    expect(within(cartao).getByText('Destino: Cerulean Cave')).toBeInTheDocument()

    fireEvent.click(within(cartao).getByRole('button', { name: 'Ver relatorio' }))
    await esvaziarMicrotarefas()

    expect(screen.getByText('Tela do relatorio aberta')).toBeInTheDocument()
  })

  it('o historico limita a quantidade mostrada e explica a regra', async () => {
    const terminadas = Array.from({ length: 7 }, (_, indice) =>
      expedicaoLerExemplo({
        id: `expedicao-historico-${indice}`,
        treinador_nome: `Treinador${indice}`,
        status: 'CONCLUIDA_SUCESSO',
        estado_observado: 'CONCLUIDA_SUCESSO',
        segundos_restantes: null,
        // Quanto maior o indice, mais recente: a mais nova e Treinador6.
        started_at: `2026-01-0${(indice % 9) + 1}T12:00:00Z`,
      }),
    )
    const { fetchMock } = montarFetchMock({ ativas: [], historico: terminadas })
    vi.stubGlobal('fetch', fetchMock)

    renderizar()
    await esvaziarMicrotarefas()

    const secaoHistorico = screen.getByRole('region', { name: 'Historico de expedicoes' })
    expect(within(secaoHistorico).getByText('As 5 mais recentes.')).toBeInTheDocument()
    expect(within(secaoHistorico).getAllByRole('article')).toHaveLength(5)
    expect(within(secaoHistorico).getByRole('article', { name: /Treinador6/i })).toBeInTheDocument()
    expect(
      within(secaoHistorico).queryByRole('article', { name: /Treinador0$/i }),
    ).not.toBeInTheDocument()

    // Achado 1 (revisao da Fase 7): o corte precisa acontecer NA BUSCA, nao
    // so na tela — a chamada ao historico pede um `limite` ao servidor em vez
    // de baixar as sete expedicoes para descartar duas depois de chegarem.
    const chamadaHistorico = fetchMock.mock.calls.find(([url]) =>
      String(url).includes('CONCLUIDA_SUCESSO'),
    )
    expect(String(chamadaHistorico?.[0])).toEqual(expect.stringContaining('limite='))
  })
})
