import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { erroExemplo, respostaTreinadoresExemplo } from '@/api/fixtures'
import { Treinadores } from '@/pages/Treinadores'

function respostaJson(corpo: unknown, status = 200) {
  return { ok: status < 400, status, json: async () => corpo }
}

function renderTreinadores() {
  return render(
    <MemoryRouter>
      <Treinadores />
    </MemoryRouter>,
  )
}

describe('Treinadores', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  it('mostra os tres treinadores, todos de nivel 1, sem Pokemon e disponiveis', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respostaJson(respostaTreinadoresExemplo())))

    renderTreinadores()

    expect(await screen.findByText('Ash')).toBeInTheDocument()
    expect(screen.getByText('Misty')).toBeInTheDocument()
    expect(screen.getByText('Brock')).toBeInTheDocument()

    expect(screen.getAllByText('Nv. 1')).toHaveLength(3)
    expect(screen.getAllByText('Disponivel')).toHaveLength(3)
    expect(
      screen.getAllByText('Sem Pokemon no time. Monte o time para despachar expedicoes.'),
    ).toHaveLength(3)
  })

  it('exibe mensagem de erro do servidor e permite tentar novamente', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          respostaJson(erroExemplo('ERRO_INTERNO', 'Nao foi possivel carregar os treinadores.'), 500),
        ),
    )

    renderTreinadores()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Nao foi possivel carregar os treinadores.',
    )
    expect(screen.getByRole('button', { name: /tentar novamente/i })).toBeInTheDocument()
  })
})
