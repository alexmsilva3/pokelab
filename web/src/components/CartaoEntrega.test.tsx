import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { entregaLerExemplo, respostaClaimEntregaExemplo } from '@/api/fixtures'
import { CartaoEntrega } from '@/components/CartaoEntrega'

function respostaJson(corpo: unknown, status = 200) {
  return { ok: status < 400, status, json: async () => corpo }
}

describe('CartaoEntrega', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('entrega em curso mostra "Receber entrega" e o tempo restante', () => {
    render(
      <CartaoEntrega
        entrega={entregaLerExemplo({ estado_observado: 'EM_CURSO', segundos_restantes: 120 })}
        onAtualizar={vi.fn()}
      />,
    )

    expect(screen.getByRole('button', { name: 'Receber entrega' })).toBeInTheDocument()
    expect(screen.getByText('02:00')).toBeInTheDocument()
  })

  it('clicar em "Receber entrega" chama o claim e mostra o resultado', async () => {
    const resposta = respostaClaimEntregaExemplo()
    const fetchMock = vi.fn().mockResolvedValue(respostaJson(resposta))
    vi.stubGlobal('fetch', fetchMock)
    const onAtualizar = vi.fn()

    render(
      <CartaoEntrega
        entrega={entregaLerExemplo({ id: 'entrega-1', estado_observado: 'EM_CURSO', segundos_restantes: 0 })}
        onAtualizar={onAtualizar}
      />,
    )

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Receber entrega' }))
      await Promise.resolve()
      await Promise.resolve()
    })

    expect(screen.getByText(/Pidgey \(Nv\. 4\)/)).toBeInTheDocument()
    expect(screen.getByText('240')).toBeInTheDocument()
    expect(onAtualizar).toHaveBeenCalled()
  })

  it('recusa ENTREGA_EM_CURSO mostra a mensagem do servidor', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        respostaJson(
          { erro: { codigo: 'ENTREGA_EM_CURSO', mensagem: 'O treinador ainda nao voltou.' } },
          409,
        ),
      ),
    )

    render(
      <CartaoEntrega
        entrega={entregaLerExemplo({ estado_observado: 'EM_CURSO', segundos_restantes: 30 })}
        onAtualizar={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Receber entrega' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('O treinador ainda nao voltou.')
  })

  it('entrega concluida ou descartada nao mostra acao nenhuma', () => {
    const { rerender } = render(
      <CartaoEntrega entrega={entregaLerExemplo({ estado_observado: 'CONCLUIDA' })} onAtualizar={vi.fn()} />,
    )
    expect(screen.getByText('Concluida')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Receber entrega' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Aceitar' })).not.toBeInTheDocument()

    rerender(
      <CartaoEntrega entrega={entregaLerExemplo({ estado_observado: 'DESCARTADA' })} onAtualizar={vi.fn()} />,
    )
    expect(screen.getByText('Descartada')).toBeInTheDocument()
  })
})
