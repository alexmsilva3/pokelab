import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { especieAvistadaExemplo } from '@/api/fixtures'
import { EspeciesAvistadas } from '@/components/EspeciesAvistadas'

describe('EspeciesAvistadas', () => {
  it('local sem avistamento mostra o vazio que convida, sem contagem de especies', () => {
    render(<EspeciesAvistadas especies={[]} />)

    expect(
      screen.getByText(
        'Nenhum Pokemon avistado aqui ainda. Mande um treinador para descobrir o que mora neste lugar.',
      ),
    ).toBeInTheDocument()

    // Regra 10 da spec 005: nem o numero de especies que faltam pode vazar.
    expect(screen.queryByText(/\d+\s*(de|\/)\s*\d+/)).not.toBeInTheDocument()
  })

  it('local com avistamento lista a especie, o sprite e quantas vezes foi vista', () => {
    render(
      <EspeciesAvistadas
        especies={[
          especieAvistadaExemplo({ especie_id: 16, nome: 'Pidgey', vezes_visto: 3 }),
          especieAvistadaExemplo({ especie_id: 19, nome: 'Rattata', vezes_visto: 1 }),
        ]}
      />,
    )

    expect(screen.getByRole('img', { name: 'Pidgey' })).toBeInTheDocument()
    expect(screen.getByText('Avistado 3 vezes')).toBeInTheDocument()

    expect(screen.getByRole('img', { name: 'Rattata' })).toBeInTheDocument()
    expect(screen.getByText('Avistado 1 vez')).toBeInTheDocument()

    expect(
      screen.queryByText(
        'Nenhum Pokemon avistado aqui ainda. Mande um treinador para descobrir o que mora neste lugar.',
      ),
    ).not.toBeInTheDocument()
  })
})
