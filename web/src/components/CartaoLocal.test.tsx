import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { localNoMapaExemplo } from '@/api/fixtures'
import { CartaoLocal } from '@/components/CartaoLocal'

describe('CartaoLocal', () => {
  it('local visitado mostra o nome e o estado em texto', () => {
    render(
      <CartaoLocal
        local={localNoMapaExemplo({ nome: 'Pallet Town', estado: 'VISITADO' })}
        onSelecionar={vi.fn()}
      />,
    )

    expect(screen.getByText('Pallet Town')).toBeInTheDocument()
    expect(screen.getByText('Visitado')).toBeInTheDocument()
  })

  it('local alcancavel mostra de onde a ida partiria e quanto tempo leva', () => {
    render(
      <CartaoLocal
        local={localNoMapaExemplo({
          id: 'route-1',
          nome: 'Route 1',
          estado: 'ALCANCAVEL',
          origem_id: 'pallet-town',
          origem_nome: 'Pallet Town',
          duracao_estimada_minutos: 7,
        })}
        onSelecionar={vi.fn()}
      />,
    )

    expect(screen.getByText('Alcancavel')).toBeInTheDocument()
    expect(screen.getByText('De Pallet Town, 7 min')).toBeInTheDocument()
  })

  it('local fora de alcance mostra o que falta visitar primeiro', () => {
    render(
      <CartaoLocal
        local={localNoMapaExemplo({
          id: 'pewter-city',
          nome: 'Pewter City',
          estado: 'FORA_DE_ALCANCE',
          origem_id: null,
          origem_nome: null,
          duracao_estimada_minutos: null,
          proximo_passo_id: 'route-1',
          proximo_passo_nome: 'Route 1',
        })}
        onSelecionar={vi.fn()}
      />,
    )

    expect(screen.getByText('Fora de alcance')).toBeInTheDocument()
    expect(screen.getByText('Visite Route 1 antes.')).toBeInTheDocument()
    // Fora de alcance nao mostra origem nem duracao: nao ha ida possivel ainda.
    expect(screen.queryByText(/^De /)).not.toBeInTheDocument()
  })

  it('clicar no cartao notifica a selecao pelo id do local', () => {
    const onSelecionar = vi.fn()
    render(
      <CartaoLocal local={localNoMapaExemplo({ id: 'pallet-town' })} onSelecionar={onSelecionar} />,
    )

    fireEvent.click(screen.getByRole('button'))

    expect(onSelecionar).toHaveBeenCalledWith('pallet-town')
  })
})
