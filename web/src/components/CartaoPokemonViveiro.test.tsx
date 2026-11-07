import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { pokemonResumoExemplo } from '@/api/fixtures'
import { CartaoPokemonViveiro } from '@/components/CartaoPokemonViveiro'

describe('CartaoPokemonViveiro', () => {
  it('mostra nome e nivel do Pokemon', () => {
    render(
      <CartaoPokemonViveiro
        pokemon={pokemonResumoExemplo({ nome: 'Pidgey', nivel: 4 })}
        soltando={false}
        onSoltar={vi.fn()}
      />,
    )

    expect(screen.getByText('Pidgey')).toBeInTheDocument()
    expect(screen.getByText('Nv. 4')).toBeInTheDocument()
  })

  it('clicar em soltar chama o callback', () => {
    const onSoltar = vi.fn()
    render(
      <CartaoPokemonViveiro
        pokemon={pokemonResumoExemplo({ nome: 'Pidgey' })}
        soltando={false}
        onSoltar={onSoltar}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Soltar' }))

    expect(onSoltar).toHaveBeenCalled()
  })

  it('enquanto solta, o botao fica desabilitado e muda de texto', () => {
    render(
      <CartaoPokemonViveiro
        pokemon={pokemonResumoExemplo({ nome: 'Pidgey' })}
        soltando={true}
        onSoltar={vi.fn()}
      />,
    )

    expect(screen.getByRole('button', { name: 'Soltando...' })).toBeDisabled()
  })
})
