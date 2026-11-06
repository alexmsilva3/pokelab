import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { pokemonResumoExemplo, treinadorResumoExemplo } from '@/api/fixtures'
import { CartaoTreinador } from '@/components/CartaoTreinador'

describe('CartaoTreinador', () => {
  it('treinador sem Pokemon convida a montar o time, em vez de parecer vazio por erro', () => {
    render(
      <CartaoTreinador treinador={treinadorResumoExemplo({ time: [] })} onSelecionar={vi.fn()} />,
    )

    expect(
      screen.getByText('Sem Pokemon no time. Monte o time para despachar expedicoes.'),
    ).toBeInTheDocument()
  })

  it('mostra nome, status, nivel e capacidade de bagagem', () => {
    render(
      <CartaoTreinador
        treinador={treinadorResumoExemplo({
          nome: 'Misty',
          status: 'EM_EXPEDICAO',
          nivel: 7,
          capacidade_bagagem: 4,
          time: [pokemonResumoExemplo({ id: 'poke-1', nome: 'Staryu' })],
        })}
        onSelecionar={vi.fn()}
      />,
    )

    expect(screen.getByText('Misty')).toBeInTheDocument()
    expect(screen.getByText('Em expedicao')).toBeInTheDocument()
    expect(screen.getByText('Nv. 7')).toBeInTheDocument()
    expect(screen.getByText('Bagagem: 4 vagas')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Staryu' })).toBeInTheDocument()
  })

  it('clicar no cartao notifica a selecao pelo id do treinador', () => {
    const onSelecionar = vi.fn()
    render(
      <CartaoTreinador
        treinador={treinadorResumoExemplo({ id: 'treinador-9' })}
        onSelecionar={onSelecionar}
      />,
    )

    fireEvent.click(screen.getByRole('button'))

    expect(onSelecionar).toHaveBeenCalledWith('treinador-9')
  })
})
