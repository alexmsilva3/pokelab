import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Login } from '@/pages/Login'
import { laboratorioExemplo } from '@/api/fixtures'
import { erroExemplo } from '@/api/fixtures'

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/laboratorio" element={<p>Tela do laboratorio</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

async function preencherEEnviar(usuario: string, senha: string) {
  fireEvent.change(screen.getByLabelText('Usuario'), { target: { value: usuario } })
  fireEvent.change(screen.getByLabelText('Senha'), { target: { value: senha } })
  fireEvent.click(screen.getByRole('button', { name: /entrar/i }))
}

describe('Login', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('com credenciais validas guarda o token e navega para o laboratorio', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          token: 'token-valido',
          professor: { id: '1', usuario: 'ash', nome_exibicao: null },
          laboratorio: laboratorioExemplo(),
        }),
      }),
    )

    renderLogin()
    await preencherEEnviar('ash', 'senhasecreta')

    expect(await screen.findByText('Tela do laboratorio')).toBeInTheDocument()
    expect(window.localStorage.getItem('pokelab:sessao')).toContain('token-valido')
  })

  it('com credenciais invalidas mostra a mensagem de erro que o servidor mandou', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => (erroExemplo('CREDENCIAIS_INVALIDAS', 'Usuario ou senha incorretos.')),
      }),
    )

    renderLogin()
    await preencherEEnviar('ash', 'senhaerrada')

    expect(await screen.findByRole('alert')).toHaveTextContent('Usuario ou senha incorretos.')
    expect(window.localStorage.getItem('pokelab:sessao')).toBeNull()
  })
})
