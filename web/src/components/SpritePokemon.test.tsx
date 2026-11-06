import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { SpritePokemon } from '@/components/SpritePokemon'

describe('SpritePokemon', () => {
  it('mostra a imagem com alt do nome quando o caminho existe', () => {
    render(<SpritePokemon caminho="1-front.png" nome="Bulbasaur" />)

    const imagem = screen.getByRole('img', { name: 'Bulbasaur' })
    expect(imagem).toBeInTheDocument()
    expect(imagem.getAttribute('src')).toContain('1-front.png')
  })

  it('sem caminho mostra a silhueta descrevendo que a especie e desconhecida', () => {
    render(<SpritePokemon caminho={null} nome={null} numero={150} />)

    expect(screen.queryByRole('img', { name: /bulbasaur/i })).not.toBeInTheDocument()
    expect(screen.getByRole('img', { name: /numero 150, ainda nao avistada/i })).toBeInTheDocument()
  })
})
