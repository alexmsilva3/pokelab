import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { capturaDoRelatorioExemplo } from '@/api/fixtures'
import { CapturasDoRelatorio } from '@/components/CapturasDoRelatorio'

describe('CapturasDoRelatorio', () => {
  it('mostra a especie e o nivel de cada captura', () => {
    render(
      <CapturasDoRelatorio
        capturas={[
          capturaDoRelatorioExemplo({
            pokemon_id: 'poke-1',
            especie_nome: 'Caterpie',
            nivel: 5,
          }),
        ]}
      />,
    )

    expect(screen.getByText('Caterpie')).toBeInTheDocument()
    expect(screen.getByText('Nv. 5')).toBeInTheDocument()
  })

  it('lista vazia convida a levar Pokebolas na proxima, sem quebrar a tela', () => {
    render(<CapturasDoRelatorio capturas={[]} />)

    expect(
      screen.getByText(
        'Nenhuma captura nesta expedicao. Leve Pokebolas e deixe espaco na bagagem na proxima.',
      ),
    ).toBeInTheDocument()
  })
})
