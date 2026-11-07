import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { pokemonDetalheExemplo } from '@/api/fixtures'
import { BarraDeExperiencia } from '@/components/BarraDeExperiencia'

describe('BarraDeExperiencia', () => {
  it('anuncia a fracao do degrau atual, nao o total acumulado', () => {
    const detalhe = pokemonDetalheExemplo({
      experiencia_vencida_no_nivel: 40,
      experiencia_do_nivel: 100,
    })

    render(<BarraDeExperiencia detalhe={detalhe} />)

    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '40')
  })

  it('mostra os numeros exatos junto da barra', () => {
    // A barra da a nocao; o texto da a conta. Quem planeja a proxima expedicao
    // precisa do numero, nao so da sensacao.
    const detalhe = pokemonDetalheExemplo({
      nivel: 7,
      experiencia_vencida_no_nivel: 40,
      experiencia_do_nivel: 100,
      experiencia_para_proximo_nivel: 60,
    })

    render(<BarraDeExperiencia detalhe={detalhe} />)

    expect(screen.getByText(/40 de 100 para o nivel 8/)).toBeInTheDocument()
    expect(screen.getByText(/Faltam 60/)).toBeInTheDocument()
  })

  it('no piso do nivel a barra fica vazia', () => {
    const detalhe = pokemonDetalheExemplo({
      experiencia_vencida_no_nivel: 0,
      experiencia_do_nivel: 100,
    })

    render(<BarraDeExperiencia detalhe={detalhe} />)

    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '0')
  })

  it('no nivel maximo a barra enche e o texto diz isso', () => {
    // Degrau de tamanho zero so acontece no teto. Cheia e a leitura honesta:
    // o Pokemon chegou. Vazia diria o contrario.
    const detalhe = pokemonDetalheExemplo({
      nivel: 100,
      nivel_maximo: true,
      experiencia_vencida_no_nivel: 0,
      experiencia_do_nivel: 0,
      experiencia_para_proximo_nivel: null,
    })

    render(<BarraDeExperiencia detalhe={detalhe} />)

    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100')
    expect(screen.getByText('Nivel maximo atingido.')).toBeInTheDocument()
  })

  it('a barra nao passa de cem por cento com numeros incoerentes', () => {
    // Defesa contra contrato quebrado: se o servidor mandar vencida > tamanho,
    // a barra satura em vez de estourar o trilho.
    const detalhe = pokemonDetalheExemplo({
      experiencia_vencida_no_nivel: 500,
      experiencia_do_nivel: 100,
    })

    render(<BarraDeExperiencia detalhe={detalhe} />)

    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100')
  })
})
