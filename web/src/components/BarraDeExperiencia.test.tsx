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

  it('o numero exato chega a leitor de tela sem depender de hover', () => {
    // O texto so aparece visualmente ao passar o mouse ou focar o trilho. Para
    // leitor de tela ele nunca esta escondido: esconder o numero de quem nao ve
    // a barra seria esconder a informacao inteira. Por isso vai em
    // `aria-valuetext`, que e o que o leitor anuncia no lugar da porcentagem.
    const detalhe = pokemonDetalheExemplo({
      nivel: 7,
      experiencia_vencida_no_nivel: 40,
      experiencia_do_nivel: 100,
      experiencia_para_proximo_nivel: 60,
    })

    render(<BarraDeExperiencia detalhe={detalhe} />)

    expect(screen.getByRole('progressbar')).toHaveAttribute(
      'aria-valuetext',
      '40 de 100 para o nivel 8. Faltam 60.',
    )
  })

  it('o trilho e alcancavel pelo teclado, para o texto nao depender de mouse', () => {
    // Hover sozinho exclui tela de toque e navegacao por teclado. O trilho
    // focalizavel e o que faz o texto aparecer para quem usa Tab.
    render(<BarraDeExperiencia detalhe={pokemonDetalheExemplo()} />)

    expect(screen.getByRole('progressbar')).toHaveAttribute('tabindex', '0')
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
