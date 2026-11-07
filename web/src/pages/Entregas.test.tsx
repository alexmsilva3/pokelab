import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { entregaLerExemplo, respostaEntregasExemplo } from '@/api/fixtures'
import type { EntregaLer, RespostaEntregas } from '@/api/tipos'
import { Entregas } from '@/pages/Entregas'

function respostaJson(corpo: unknown, status = 200) {
  return { ok: status < 400, status, json: async () => corpo }
}

function montarFetchMock(resposta: RespostaEntregas, respostaRefresh?: RespostaEntregas) {
  return vi.fn((url: unknown, init?: RequestInit) => {
    const caminho = String(url)
    if (init?.method === 'POST' && caminho.endsWith('/refresh')) {
      return Promise.resolve(respostaJson(respostaRefresh ?? resposta))
    }
    if (caminho.includes('/deliveries')) {
      return Promise.resolve(respostaJson(resposta))
    }
    throw new Error(`Chamada inesperada no mock de fetch: ${caminho}`)
  })
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
      <Entregas />
    </MemoryRouter>,
  )
}

describe('Entregas', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('mostra requisitos, destino, duracao e recompensa de cada pedido', async () => {
    const entrega = entregaLerExemplo({
      titulo: 'Encomenda para Cerulean City',
      local_destino_nome: 'Cerulean City',
      requisitos: [
        { especie_id: 16, especie_nome: 'Pidgey', quantidade: 2, disponiveis_no_viveiro: 4 },
      ],
      duracao_minutos: 12,
      recompensa_moedas: 240,
    })
    vi.stubGlobal('fetch', montarFetchMock(respostaEntregasExemplo({ items: [entrega] })))

    renderizar()
    await esvaziarMicrotarefas()

    const cartao = screen.getByRole('article', { name: 'Encomenda para Cerulean City' })
    expect(within(cartao).getByText('Destino: Cerulean City')).toBeInTheDocument()
    expect(within(cartao).getByText(/Pidgey: 2 pedidos, 4 no viveiro/)).toBeInTheDocument()
    expect(within(cartao).getByText('12 min')).toBeInTheDocument()
    expect(within(cartao).getByText('240 moedas')).toBeInTheDocument()
  })

  it('mostra quanto falta para o pedido vencer', async () => {
    const entrega = entregaLerExemplo({ segundos_para_expirar: 90 })
    vi.stubGlobal('fetch', montarFetchMock(respostaEntregasExemplo({ items: [entrega] })))

    renderizar()
    await esvaziarMicrotarefas()

    expect(screen.getByText('01:30')).toBeInTheDocument()
  })

  it('pedido expirado aparece como tal, sem botao de aceitar', async () => {
    const entrega = entregaLerExemplo({
      estado_observado: 'EXPIRADA',
      segundos_para_expirar: null,
      atendivel: false,
    })
    vi.stubGlobal('fetch', montarFetchMock(respostaEntregasExemplo({ items: [entrega] })))

    renderizar()
    await esvaziarMicrotarefas()

    expect(screen.getByText('Expirada')).toBeInTheDocument()
    expect(screen.getByText(/Este pedido venceu sem aceite/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Aceitar' })).not.toBeInTheDocument()
  })

  it('pedido nao atendivel mostra o motivo do servidor em vez do botao de aceitar', async () => {
    const entrega = entregaLerExemplo({ atendivel: false, motivo: 'Faltam 2 Pidgey no viveiro.' })
    vi.stubGlobal('fetch', montarFetchMock(respostaEntregasExemplo({ items: [entrega] })))

    renderizar()
    await esvaziarMicrotarefas()

    expect(screen.getByText('Faltam 2 Pidgey no viveiro.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Aceitar' })).not.toBeInTheDocument()
  })

  it('com vaga para repor, so o botao "Repor vagas" aparece', async () => {
    vi.stubGlobal(
      'fetch',
      montarFetchMock(respostaEntregasExemplo({ vagas_para_repor: 1, segundos_para_regerar: 300 })),
    )

    renderizar()
    await esvaziarMicrotarefas()

    expect(screen.getByRole('button', { name: 'Repor vagas' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Regerar lista' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Repor vagas' })).not.toBeDisabled()
    expect(screen.queryByText(/Disponivel em/)).not.toBeInTheDocument()
  })

  it('sem vaga e com intervalo pendente, "Regerar lista" aparece desabilitado com a contagem', async () => {
    vi.stubGlobal(
      'fetch',
      montarFetchMock(respostaEntregasExemplo({ vagas_para_repor: 0, segundos_para_regerar: 300 })),
    )

    renderizar()
    await esvaziarMicrotarefas()

    expect(screen.queryByRole('button', { name: 'Repor vagas' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Regerar lista' })).toBeDisabled()
    expect(screen.getByText('05:00')).toBeInTheDocument()
  })

  it('sem vaga e sem intervalo pendente, "Regerar lista" fica habilitado', async () => {
    vi.stubGlobal(
      'fetch',
      montarFetchMock(respostaEntregasExemplo({ vagas_para_repor: 0, segundos_para_regerar: 0 })),
    )

    renderizar()
    await esvaziarMicrotarefas()

    expect(screen.getByRole('button', { name: 'Regerar lista' })).not.toBeDisabled()
  })

  it('clicar em "Repor vagas" chama o refresh e atualiza a lista', async () => {
    const entregaNova = entregaLerExemplo({ id: 'entrega-nova', titulo: 'Encomenda para Pewter City' })
    const fetchMock = montarFetchMock(
      respostaEntregasExemplo({ vagas_para_repor: 1 }),
      respostaEntregasExemplo({ items: [entregaNova], vagas_para_repor: 0 }),
    )
    vi.stubGlobal('fetch', fetchMock)

    renderizar()
    await esvaziarMicrotarefas()

    fireEvent.click(screen.getByRole('button', { name: 'Repor vagas' }))
    await esvaziarMicrotarefas()

    expect(fetchMock.mock.calls.some(([url, init]) => String(url).endsWith('/refresh') && init?.method === 'POST')).toBe(true)
    expect(screen.getByText('Encomenda para Pewter City')).toBeInTheDocument()
  })

  it('recusa AGUARDE_PARA_REGERAR mostra a mensagem do servidor', async () => {
    const fetchMock = vi.fn((url: unknown, init?: RequestInit) => {
      const caminho = String(url)
      if (init?.method === 'POST' && caminho.endsWith('/refresh')) {
        return Promise.resolve(
          respostaJson(
            {
              erro: {
                codigo: 'AGUARDE_PARA_REGERAR',
                mensagem: 'Aguarde 5 minutos para regerar a lista.',
              },
            },
            409,
          ),
        )
      }
      return Promise.resolve(
        respostaJson(respostaEntregasExemplo({ vagas_para_repor: 0, segundos_para_regerar: 0 })),
      )
    })
    vi.stubGlobal('fetch', fetchMock)

    renderizar()
    await esvaziarMicrotarefas()

    fireEvent.click(screen.getByRole('button', { name: 'Regerar lista' }))
    await esvaziarMicrotarefas()

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Aguarde 5 minutos para regerar a lista.',
    )
  })

  it('lista vazia orienta o professor a repor vagas', async () => {
    vi.stubGlobal('fetch', montarFetchMock(respostaEntregasExemplo({ items: [], vagas_para_repor: 3 })))

    renderizar()
    await esvaziarMicrotarefas()

    expect(screen.getByText(/Nenhum pedido ativo agora/)).toBeInTheDocument()
  })

  it('o contador de expirar decresce localmente e se corrige pelo servidor', async () => {
    const entrega = entregaLerExemplo({ id: 'entrega-1', segundos_para_expirar: 5 })
    const entregaExpirada = entregaLerExemplo({
      id: 'entrega-1',
      estado_observado: 'EXPIRADA',
      segundos_para_expirar: null,
      atendivel: false,
    })

    let atual: EntregaLer = entrega
    const fetchMock = vi.fn((url: unknown) => {
      const caminho = String(url)
      if (caminho.includes('/deliveries')) {
        return Promise.resolve(respostaJson(respostaEntregasExemplo({ items: [atual] })))
      }
      throw new Error(`Chamada inesperada no mock de fetch: ${caminho}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    renderizar()
    await esvaziarMicrotarefas()
    expect(screen.getByText('00:05')).toBeInTheDocument()

    atual = entregaExpirada
    await act(async () => {
      vi.advanceTimersByTime(5000)
    })
    await esvaziarMicrotarefas()

    expect(screen.getByText('Expirada')).toBeInTheDocument()
  })
})
