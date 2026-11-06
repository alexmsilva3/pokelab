import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  entradaPokedexCapturadaExemplo,
  entradaPokedexDesconhecidaExemplo,
  entradaPokedexVistaExemplo,
  erroExemplo,
  pokedexExemplo,
} from '@/api/fixtures'
import { Pokedex } from '@/pages/Pokedex'

function respostaJson(corpo: unknown, status = 200) {
  return { ok: status < 400, status, json: async () => corpo }
}

function renderPokedex() {
  return render(
    <MemoryRouter>
      <Pokedex />
    </MemoryRouter>,
  )
}

describe('Pokedex', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  it('mostra as tres aparencias: capturada, vista e desconhecida', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        respostaJson(
          pokedexExemplo({
            items: [
              entradaPokedexCapturadaExemplo({ numero: 1, nome: 'Bulbasaur', quantidade: 2 }),
              entradaPokedexVistaExemplo({ numero: 4, nome: 'Charmander' }),
              entradaPokedexDesconhecidaExemplo({ numero: 150 }),
            ],
            capturadas: 1,
            vistas: 2,
          }),
        ),
      ),
    )

    renderPokedex()

    expect(await screen.findByText('Bulbasaur')).toBeInTheDocument()
    expect(screen.getByText('Capturada (2)')).toBeInTheDocument()

    expect(screen.getByText('Charmander')).toBeInTheDocument()
    expect(screen.getByText('Nao capturada')).toBeInTheDocument()

    expect(screen.getByText('1 capturadas e 2 vistas de 151')).toBeInTheDocument()
  })

  it('especie nunca vista nao mostra nome em lugar nenhum da tela', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        respostaJson(
          pokedexExemplo({
            items: [entradaPokedexDesconhecidaExemplo({ numero: 150 })],
            capturadas: 0,
            vistas: 0,
          }),
        ),
      ),
    )

    renderPokedex()

    expect(await screen.findByRole('img', { name: /numero 150/i })).toBeInTheDocument()
    // Mewtwo e a especie 150 do seed: se o nome vazasse para a tela de
    // qualquer jeito (atributo, texto escondido), apareceria aqui.
    expect(screen.queryByText(/mewtwo/i)).not.toBeInTheDocument()
  })

  it('exibe mensagem de erro do servidor e permite tentar novamente', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        respostaJson(
          erroExemplo('ERRO_INTERNO', 'Nao foi possivel carregar a Pokedex.'),
          500,
        ),
      ),
    )

    renderPokedex()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Nao foi possivel carregar a Pokedex.',
    )
    expect(screen.getByRole('button', { name: /tentar novamente/i })).toBeInTheDocument()
  })
})
