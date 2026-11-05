import { Navigate, Outlet } from 'react-router-dom'
import { useSessao } from '@/store/auth'

/** Sem sessao valida, nao ha tela de jogo: o professor volta para o login. */
export function RotaProtegida() {
  const sessao = useSessao()

  if (!sessao) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
