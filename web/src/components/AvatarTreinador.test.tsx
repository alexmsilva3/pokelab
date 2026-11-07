import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { avatarTreinadorExemplo } from '@/api/fixtures'
import { AvatarTreinador } from '@/components/AvatarTreinador'

describe('AvatarTreinador', () => {
  it('mostra as iniciais e descreve de quem e o retrato', () => {
    render(<AvatarTreinador avatar={avatarTreinadorExemplo()} nome="Ash" />)

    const retrato = screen.getByRole('img', { name: 'Retrato de Ash' })
    expect(retrato).toBeInTheDocument()
    expect(retrato).toHaveTextContent('AS')
  })

  it('desenha o sprite da classe quando o servidor manda um', () => {
    const { container } = render(
      <AvatarTreinador
        avatar={avatarTreinadorExemplo({ sprite: 'treinadores/lass.png' })}
        nome="Ash"
      />,
    )

    const sprite = container.querySelector('.avatar-treinador-sprite')
    expect(sprite).toHaveAttribute('src', expect.stringContaining('treinadores/lass.png'))
  })

  it('sem sprite, as iniciais continuam sendo o retrato', () => {
    // Treinador gravado antes das classes existirem. O sprite cobre as
    // iniciais em vez de substitui-las justamente para este caso nao abrir
    // buraco na tela.
    const { container } = render(
      <AvatarTreinador avatar={avatarTreinadorExemplo({ sprite: null })} nome="Ash" />,
    )

    expect(container.querySelector('.avatar-treinador-sprite')).toBeNull()
    expect(screen.getByRole('img', { name: 'Retrato de Ash' })).toHaveTextContent('AS')
  })

  it('o sprite nao e anunciado duas vezes pelo leitor de tela', () => {
    const { container } = render(<AvatarTreinador avatar={avatarTreinadorExemplo()} nome="Ash" />)

    const sprite = container.querySelector('.avatar-treinador-sprite')
    expect(sprite).toHaveAttribute('aria-hidden', 'true')
    expect(sprite).toHaveAttribute('alt', '')
  })
})
