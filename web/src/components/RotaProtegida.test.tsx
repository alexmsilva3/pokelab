import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { RotaProtegida } from '@/components/RotaProtegida'
import { guardarSessao } from '@/store/auth'
import { laboratorioExemplo } from '@/api/fixtures'

function renderComRota(caminhoInicial: string) {
  return render(
    <MemoryRouter initialEntries={[caminhoInicial]}>
      <Routes>
        <Route path="/login" element={<p>Tela de login</p>} />
        <Route element={<RotaProtegida />}>
          <Route path="/laboratorio" element={<p>Tela do laboratorio</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('RotaProtegida', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('sem token redireciona para o login', () => {
    renderComRota('/laboratorio')

    expect(screen.getByText('Tela de login')).toBeInTheDocument()
    expect(screen.queryByText('Tela do laboratorio')).not.toBeInTheDocument()
  })

  it('com sessao valida renderiza a rota protegida', () => {
    guardarSessao({
      token: 'token-valido',
      professor: { id: '1', usuario: 'ash', nome_exibicao: null },
      laboratorio: laboratorioExemplo(),
    })

    renderComRota('/laboratorio')

    expect(screen.getByText('Tela do laboratorio')).toBeInTheDocument()
  })
})
