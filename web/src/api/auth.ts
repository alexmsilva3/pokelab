/**
 * Chamadas de autenticacao. Networking puro: quem decide o que fazer com a
 * sessao resultante e o chamador (ver src/store/auth.ts).
 */
import { request } from '@/api/client'
import type { PerfilCompleto, Sessao } from '@/api/tipos'

export interface CredenciaisRegistro {
  usuario: string
  senha: string
  nome_exibicao?: string
  nome_laboratorio?: string
}

export interface CredenciaisLogin {
  usuario: string
  senha: string
}

export function registrar(dados: CredenciaisRegistro): Promise<Sessao> {
  return request<Sessao>('/auth/register', {
    method: 'POST',
    body: JSON.stringify(dados),
  })
}

export function entrar(dados: CredenciaisLogin): Promise<Sessao> {
  return request<Sessao>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(dados),
  })
}

export function buscarPerfil(): Promise<PerfilCompleto> {
  return request<PerfilCompleto>('/me')
}
