import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Registro } from '@/pages/Registro'
import { laboratorioExemplo } from '@/api/fixtures'

function renderRegistro() {
  return render(
    <MemoryRouter initialEntries={['/registro']}>
      <Routes>
        <Route path="/registro" element={<Registro />} />
        <Route path="/laboratorio" element={<p>Tela do laboratorio</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('Registro', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('recusa senha curta antes de chamar o servidor', async () => {
    const fetchEspiado = vi.fn()
    vi.stubGlobal('fetch', fetchEspiado)

    renderRegistro()
    fireEvent.change(screen.getByLabelText('Usuario'), { target: { value: 'ash' } })
    fireEvent.change(screen.getByLabelText('Senha'), { target: { value: '1234567' } })
    fireEvent.change(screen.getByLabelText('Confirmar senha'), { target: { value: '1234567' } })
    fireEvent.click(screen.getByRole('button', { name: /criar conta/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent('no minimo 8 caracteres')
    expect(fetchEspiado).not.toHaveBeenCalled()
  })

  it('com dados validos cria a conta, guarda a sessao e navega para o laboratorio', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 201,
        json: async () => ({
          token: 'token-novo',
          professor: { id: '1', usuario: 'ash', nome_exibicao: null },
          laboratorio: laboratorioExemplo(),
        }),
      }),
    )

    renderRegistro()
    fireEvent.change(screen.getByLabelText('Usuario'), { target: { value: 'ash' } })
    fireEvent.change(screen.getByLabelText('Senha'), { target: { value: 'senhasecreta' } })
    fireEvent.change(screen.getByLabelText('Confirmar senha'), { target: { value: 'senhasecreta' } })
    fireEvent.click(screen.getByRole('button', { name: /criar conta/i }))

    expect(await screen.findByText('Tela do laboratorio')).toBeInTheDocument()
    expect(window.localStorage.getItem('pokelab:sessao')).toContain('token-novo')
  })
})
