import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AvatarTreinador } from '@/components/AvatarTreinador'

describe('AvatarTreinador', () => {
  it('mostra as iniciais e descreve de quem e o retrato', () => {
    render(<AvatarTreinador avatar={{ iniciais: 'AS', cor: '#2563a8' }} nome="Ash" />)

    const retrato = screen.getByRole('img', { name: 'Retrato de Ash' })
    expect(retrato).toBeInTheDocument()
    expect(retrato).toHaveTextContent('AS')
  })
})
