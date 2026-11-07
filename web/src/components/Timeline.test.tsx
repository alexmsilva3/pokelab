import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { eventoDeExpedicaoExemplo } from '@/api/fixtures'
import type { EventoDeExpedicao } from '@/api/tipos'
import { Timeline } from '@/components/Timeline'

describe('Timeline', () => {
  it('renderiza um item por evento, na mesma ordem que o servidor mandou', () => {
    const eventos = [
      eventoDeExpedicaoExemplo({
        ordem: 0,
        tipo: 'PARTIDA',
        texto: 'Ash partiu de Pallet Town rumo a Route 1.',
        ocorrido_em_minuto: 0,
      }),
      eventoDeExpedicaoExemplo({
        ordem: 1,
        tipo: 'BATALHA',
        texto: 'Bulbasaur enfrentou Caterpie (nivel 5) e venceu.',
        ocorrido_em_minuto: 3,
      }),
      eventoDeExpedicaoExemplo({
        ordem: 2,
        tipo: 'RETORNO',
        texto: 'Ash retornou a Pallet Town.',
        ocorrido_em_minuto: 7,
      }),
    ]

    render(<Timeline eventos={eventos} />)

    const lista = screen.getByRole('list')
    const itens = screen.getAllByRole('listitem')
    expect(itens).toHaveLength(3)

    const textos = itens.map((item) => item.textContent)
    expect(textos[0]).toContain('Ash partiu de Pallet Town rumo a Route 1.')
    expect(textos[1]).toContain('Bulbasaur enfrentou Caterpie (nivel 5) e venceu.')
    expect(textos[2]).toContain('Ash retornou a Pallet Town.')

    // Lista ordenada (<ol>), nao uma <ul> qualquer.
    expect(lista.tagName).toBe('OL')
  })

  it('mostra o minuto e o tipo do evento em texto, nao so pelo marcador', () => {
    render(
      <Timeline
        eventos={[
          eventoDeExpedicaoExemplo({
            tipo: 'EVOLUCAO',
            texto: 'Bulbasaur virou Ivysaur.',
            ocorrido_em_minuto: 12,
          }),
        ]}
      />,
    )

    expect(screen.getByText('12 min')).toBeInTheDocument()
    expect(screen.getByText('Evolucao')).toBeInTheDocument()
    expect(screen.getByText('Bulbasaur virou Ivysaur.')).toBeInTheDocument()
  })

  it('um tipo de evento desconhecido nao quebra a tela', () => {
    render(
      <Timeline
        eventos={[
          eventoDeExpedicaoExemplo({
            // Simula um tipo que o servidor venha a mandar no futuro, fora da
            // uniao fechada conhecida pelo frontend hoje.
            tipo: 'TIPO_NOVO_DO_SERVIDOR' as unknown as EventoDeExpedicao['tipo'],
            texto: 'Algo aconteceu.',
          }),
        ]}
      />,
    )

    expect(screen.getByText('Evento')).toBeInTheDocument()
    expect(screen.getByText('Algo aconteceu.')).toBeInTheDocument()
  })

  it('lista vazia nao quebra a tela', () => {
    render(<Timeline eventos={[]} />)

    expect(
      screen.getByText('Nenhum evento registrado nesta expedicao.'),
    ).toBeInTheDocument()
  })
})
