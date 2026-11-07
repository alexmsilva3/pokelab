import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { itemDoRelatorioExemplo } from '@/api/fixtures'
import { ItensDoRelatorio } from '@/components/ItensDoRelatorio'

describe('ItensDoRelatorio', () => {
  it('mostra itens consumidos e encontrados separadamente', () => {
    render(
      <ItensDoRelatorio
        consumidos={[itemDoRelatorioExemplo({ item_id: 'poke-ball', nome: 'Poke Ball', quantidade: 3 })]}
        encontrados={[itemDoRelatorioExemplo({ item_id: 'potion', nome: 'Potion', quantidade: 1 })]}
      />,
    )

    const secaoConsumidos = screen.getByRole('region', { name: 'Itens consumidos' })
    expect(within(secaoConsumidos).getByText('Poke Ball')).toBeInTheDocument()
    expect(within(secaoConsumidos).getByText('3')).toBeInTheDocument()

    const secaoEncontrados = screen.getByRole('region', { name: 'Itens encontrados' })
    expect(within(secaoEncontrados).getByText('Potion')).toBeInTheDocument()
    expect(within(secaoEncontrados).getByText('1')).toBeInTheDocument()
  })

  it('sem item nenhum, mostra o vazio sem quebrar a tela', () => {
    render(<ItensDoRelatorio consumidos={[]} encontrados={[]} />)

    expect(
      screen.getByText('Nenhum item consumido ou encontrado nesta expedicao.'),
    ).toBeInTheDocument()
  })
})
