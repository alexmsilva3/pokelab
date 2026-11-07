import { act, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { erroExemplo, expedicaoResumoExemplo, respostaExpedicoesExemplo } from '@/api/fixtures'
import type { ExpedicaoResumo } from '@/api/tipos'
import { PainelExpedicoesAtivas } from '@/components/PainelExpedicoesAtivas'

function respostaJson(corpo: unknown, status = 200) {
  return { ok: status < 400, status, json: async () => corpo }
}

function montarFetchMock(itens: ExpedicaoResumo[]) {
  return vi.fn(() =>
    Promise.resolve(respostaJson(respostaExpedicoesExemplo({ items: itens, total: itens.length }))),
  )
}

function renderizar() {
  return render(
    <MemoryRouter>
      <PainelExpedicoesAtivas />
    </MemoryRouter>,
  )
}

async function esvaziarMicrotarefas() {
  for (let i = 0; i < 10; i += 1) {
    await act(async () => {
      await Promise.resolve()
    })
  }
}

describe('PainelExpedicoesAtivas', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('mostra treinador, destino e tempo restante reusando o CartaoExpedicao', async () => {
    const ativa = expedicaoResumoExemplo({
      treinador_nome: 'Ash',
      local_destino_nome: 'Route 1',
      estado_observado: 'EM_CURSO',
      segundos_restantes: 90,
    })
    vi.stubGlobal('fetch', montarFetchMock([ativa]))

    renderizar()
    await esvaziarMicrotarefas()

    const cartao = screen.getByRole('article', { name: /Ash/i })
    expect(within(cartao).getByText('Destino: Route 1')).toBeInTheDocument()
    expect(within(cartao).getByText('01:30')).toBeInTheDocument()
  })

  it('mostra a acao de receber relatorio quando o prazo venceu', async () => {
    const aguardando = expedicaoResumoExemplo({
      treinador_nome: 'Misty',
      estado_observado: 'AGUARDANDO_RELATORIO',
      segundos_restantes: 0,
    })
    vi.stubGlobal('fetch', montarFetchMock([aguardando]))

    renderizar()
    await esvaziarMicrotarefas()

    const cartao = screen.getByRole('article', { name: /Misty/i })
    expect(within(cartao).getByRole('button', { name: 'Receber relatorio' })).toBeInTheDocument()
  })

  it('sem expedicao em andamento, orienta a despachar uma', async () => {
    vi.stubGlobal('fetch', montarFetchMock([]))

    renderizar()
    await esvaziarMicrotarefas()

    expect(screen.getByText(/Nenhuma expedicao em andamento/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /despache um treinador/i })).toHaveAttribute(
      'href',
      '/expedicoes',
    )
  })

  it('erro ao carregar oferece tentar novamente', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          respostaJson(
            erroExemplo('ERRO_INTERNO', 'Nao foi possivel carregar agora.'),
            500,
          ),
        ),
      ),
    )

    renderizar()
    await esvaziarMicrotarefas()

    expect(screen.getByRole('alert')).toHaveTextContent('Nao foi possivel carregar agora.')
    expect(screen.getByRole('button', { name: /tentar novamente/i })).toBeInTheDocument()
  })
})
