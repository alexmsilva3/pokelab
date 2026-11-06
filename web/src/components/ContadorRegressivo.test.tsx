import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ContadorRegressivo } from '@/components/ContadorRegressivo'

describe('ContadorRegressivo', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('mostra o tempo restante formatado em minutos e segundos', () => {
    render(<ContadorRegressivo segundosRestantes={125} />)

    expect(screen.getByText('02:05')).toBeInTheDocument()
  })

  it('decresce sozinho com o tempo falso, sem perguntar ao servidor a cada segundo', () => {
    render(<ContadorRegressivo segundosRestantes={10} />)

    expect(screen.getByText('00:10')).toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(3000)
    })

    expect(screen.getByText('00:07')).toBeInTheDocument()
  })

  it('se corrige para o valor do servidor em vez de continuar a propria contagem', () => {
    const { rerender } = render(<ContadorRegressivo segundosRestantes={100} />)

    act(() => {
      vi.advanceTimersByTime(5000)
    })
    expect(screen.getByText('01:35')).toBeInTheDocument()

    // Um novo poll chega com um valor BEM diferente do que a contagem local
    // teria chegado sozinha (01:30, nao 00:50): o componente tem que exibir
    // exatamente o que o servidor mandou, nunca o proprio calculo.
    rerender(<ContadorRegressivo segundosRestantes={50} />)

    expect(screen.getByText('00:50')).toBeInTheDocument()
  })

  it('ao chegar a zero, avisa o chamador em vez de declarar a expedicao terminada', () => {
    const aoChegarAZero = vi.fn()
    render(<ContadorRegressivo segundosRestantes={2} aoChegarAZero={aoChegarAZero} />)

    act(() => {
      vi.advanceTimersByTime(2000)
    })

    expect(screen.getByText('00:00')).toBeInTheDocument()
    expect(aoChegarAZero).toHaveBeenCalledTimes(1)
    // O componente so chega a zero e avisa; quem decide o que aconteceu com a
    // expedicao e o servidor, consultado por quem chama este componente.
    expect(screen.queryByText(/conclu[ií]da/i)).not.toBeInTheDocument()

    // Continuar avancando o relogio nao chama de novo: o aviso e uma unica vez.
    act(() => {
      vi.advanceTimersByTime(3000)
    })
    expect(aoChegarAZero).toHaveBeenCalledTimes(1)
  })
})
