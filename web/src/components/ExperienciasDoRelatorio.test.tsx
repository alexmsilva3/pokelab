import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ganhoDeExperienciaExemplo, pokemonDoRelatorioExemplo } from '@/api/fixtures'
import { ExperienciasDoRelatorio } from '@/components/ExperienciasDoRelatorio'

describe('ExperienciasDoRelatorio', () => {
  it('mostra as tres experiencias: time, treinador e laboratorio', () => {
    render(
      <ExperienciasDoRelatorio
        time={[pokemonDoRelatorioExemplo({ especie_nome: 'Bulbasaur', nivel_antes: 5, nivel_depois: 7 })]}
        treinador={ganhoDeExperienciaExemplo({ nivel_antes: 1, nivel_depois: 2, exp_ganha: 64 })}
        laboratorio={ganhoDeExperienciaExemplo({ nivel_antes: 1, nivel_depois: 1, exp_ganha: 160 })}
      />,
    )

    const secaoTime = screen.getByRole('region', { name: 'Experiencia do time' })
    expect(within(secaoTime).getByText('Bulbasaur')).toBeInTheDocument()
    expect(within(secaoTime).getByText('nivel 5 para 7')).toBeInTheDocument()

    const secaoTreinador = screen.getByRole('region', { name: 'Experiencia do treinador' })
    expect(within(secaoTreinador).getByText(/Nivel 1 para 2/)).toBeInTheDocument()

    const secaoLaboratorio = screen.getByRole('region', { name: 'Experiencia do laboratorio' })
    expect(within(secaoLaboratorio).getByText(/Nivel 1 para 1/)).toBeInTheDocument()
  })

  it('evolucao aparece como tal, nao so como mais uma linha de nivel', () => {
    render(
      <ExperienciasDoRelatorio
        time={[
          pokemonDoRelatorioExemplo({
            especie_nome: 'Bulbasaur',
            nivel_antes: 15,
            nivel_depois: 33,
            evoluiu_para_id: 2,
            evoluiu_para_nome: 'Ivysaur',
          }),
        ]}
        treinador={ganhoDeExperienciaExemplo()}
        laboratorio={ganhoDeExperienciaExemplo()}
      />,
    )

    expect(screen.getByText('Bulbasaur virou Ivysaur')).toBeInTheDocument()
  })

  it('time vazio nao quebra a tela', () => {
    render(
      <ExperienciasDoRelatorio
        time={[]}
        treinador={ganhoDeExperienciaExemplo()}
        laboratorio={ganhoDeExperienciaExemplo()}
      />,
    )

    expect(screen.getByText('Nenhum Pokemon participou desta expedicao.')).toBeInTheDocument()
  })
})
