import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { pokemonDetalheExemplo } from '@/api/fixtures'
import { FichaPokemon } from '@/components/FichaPokemon'

function respostaJson(corpo: unknown, status = 200) {
  return { ok: status < 400, status, json: async () => corpo }
}

describe('FichaPokemon', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  describe('campo de apelido', () => {
    it('apelido igual ao nome da especie aparece no campo de edicao', async () => {
      // A ficha deduzia "nao tem apelido" comparando nome com especie_nome.
      // Quem apelidasse um Pidgey de "Pidgey" via o campo vazio, e o proximo
      // salvar apagaria o apelido.
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue(
          respostaJson(
            pokemonDetalheExemplo({
              nome: 'Bulbasaur',
              apelido: 'Bulbasaur',
              especie_nome: 'Bulbasaur',
            }),
          ),
        ),
      )

      render(<FichaPokemon id="abc" onAtualizado={() => {}} />)

      const campo = await screen.findByLabelText(/apelido/i)
      expect(campo).toHaveValue('Bulbasaur')
    })

    it('sem apelido o campo de edicao comeca vazio', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue(
          respostaJson(
            pokemonDetalheExemplo({ nome: 'Bulbasaur', apelido: null, especie_nome: 'Bulbasaur' }),
          ),
        ),
      )

      render(<FichaPokemon id="abc" onAtualizado={() => {}} />)

      expect(await screen.findByLabelText(/apelido/i)).toHaveValue('')
    })
  })

  it('erro de gravacao nao sobrevive a troca de Pokemon', async () => {
    // O alerta de falha ficava na tela ao abrir o Pokemon seguinte, parecendo
    // que o salvamento deste e que tinha falhado.
    const detalhe = pokemonDetalheExemplo({ nome: 'Bulbasaur', apelido: null })

    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
        if (init?.method === 'PATCH') {
          return Promise.resolve(respostaJson({ erro: { codigo: 'X', mensagem: 'Falhou' } }, 500))
        }
        return Promise.resolve(respostaJson(detalhe))
      }),
    )

    const { rerender } = render(<FichaPokemon id="primeiro" onAtualizado={() => {}} />)

    fireEvent.change(await screen.findByLabelText(/apelido/i), {
      target: { value: 'Folhinha' },
    })
    fireEvent.click(screen.getByRole('button', { name: /salvar/i }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()

    rerender(<FichaPokemon id="segundo" onAtualizado={() => {}} />)

    await waitFor(() => {
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })
  })
})
