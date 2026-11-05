import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  laboratorioExemplo,
  perfilExemplo,
  resumoExemplo,
  sessaoExemplo,
} from '@/api/fixtures'
import { Laboratorio } from '@/pages/Laboratorio'
import { guardarSessao } from '@/store/auth'

function renderLaboratorio() {
  return render(
    <MemoryRouter>
      <Laboratorio />
    </MemoryRouter>,
  )
}

describe('Laboratorio', () => {
  beforeEach(() => {
    window.localStorage.clear()
    guardarSessao(sessaoExemplo())
  })

  it('mostra os dados do laboratorio vindos do /me', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () =>
          perfilExemplo({
            laboratorio: laboratorioExemplo({ nivel: 2, experiencia: 40, moedas: 120 }),
          }),
      }),
    )

    renderLaboratorio()

    expect(await screen.findByRole('heading', { name: 'Lab Pallet' })).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText('120')).toBeInTheDocument()
    expect(screen.getByText('Professor Ash')).toBeInTheDocument()
    expect(screen.queryByText(/nenhum treinador/i)).not.toBeInTheDocument()
  })

  it('sem treinador no laboratorio orienta o professor a recrutar um', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () =>
          perfilExemplo({
            resumo: resumoExemplo({
              pokemon: 0,
              treinadores: 0,
              especies_vistas: 0,
              especies_capturadas: 0,
            }),
          }),
      }),
    )

    renderLaboratorio()

    expect(
      await screen.findByText('Nenhum treinador no laboratorio. Recrute um para comecar a despachar expedicoes.'),
    ).toBeInTheDocument()
  })

  it('exibe mensagem de erro do servidor e permite tentar novamente', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => ({
          erro: { codigo: 'ERRO_INTERNO', mensagem: 'Nao foi possivel carregar o laboratorio agora.' },
        }),
      }),
    )

    renderLaboratorio()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Nao foi possivel carregar o laboratorio agora.',
    )
    expect(screen.getByRole('button', { name: /tentar novamente/i })).toBeInTheDocument()
  })
})
