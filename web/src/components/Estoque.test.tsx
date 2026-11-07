import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { itemEstoqueExemplo } from '@/api/fixtures'
import { Estoque } from '@/components/Estoque'

describe('Estoque', () => {
  it('agrupa os itens por categoria', () => {
    render(
      <Estoque
        itens={[
          itemEstoqueExemplo({ item_id: 'poke-ball', nome: 'Poke Ball', categoria: 'POKEBOLA', quantidade: 10 }),
          itemEstoqueExemplo({ item_id: 'potion', nome: 'Potion', categoria: 'CURA', quantidade: 5 }),
        ]}
      />,
    )

    expect(screen.getByRole('heading', { name: 'Pokebolas' })).toBeInTheDocument()
    expect(screen.getByText('Poke Ball')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Cura' })).toBeInTheDocument()
    expect(screen.getByText('Potion')).toBeInTheDocument()
  })

  it('nao mostra item com quantidade zero', () => {
    render(
      <Estoque
        itens={[
          itemEstoqueExemplo({ item_id: 'poke-ball', nome: 'Poke Ball', categoria: 'POKEBOLA', quantidade: 10 }),
          itemEstoqueExemplo({ item_id: 'revive', nome: 'Revive', categoria: 'REVIVE', quantidade: 0 }),
        ]}
      />,
    )

    expect(screen.getByText('Poke Ball')).toBeInTheDocument()
    expect(screen.queryByText('Revive')).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Revive' })).not.toBeInTheDocument()
  })

  it('estoque vazio orienta o professor a repor', () => {
    render(<Estoque itens={[]} />)

    expect(
      screen.getByText('O estoque esta vazio. Conclua expedicoes ou entregas para repor.'),
    ).toBeInTheDocument()
  })
})
