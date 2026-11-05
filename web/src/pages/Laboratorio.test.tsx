import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Laboratorio } from '@/pages/Laboratorio'

describe('Laboratorio', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: 'ok' }),
      }),
    )
  })

  it('renderiza o titulo do projeto', async () => {
    render(<Laboratorio />)
    expect(await screen.findByRole('heading', { name: 'PokeLab' })).toBeInTheDocument()
    await screen.findByText('API: online')
  })

  it('reporta o estado da API', async () => {
    render(<Laboratorio />)
    expect(await screen.findByText('API: online')).toBeInTheDocument()
  })
})
