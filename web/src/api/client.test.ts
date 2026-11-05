import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, request } from '@/api/client'
import { guardarSessao } from '@/store/auth'
import { laboratorioExemplo } from '@/api/fixtures'

describe('request', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('numa resposta 401 com sessao ativa, limpa a sessao guardada', async () => {
    guardarSessao({
      token: 'token-expirado',
      professor: { id: '1', usuario: 'ash', nome_exibicao: null },
      laboratorio: laboratorioExemplo(),
    })

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({
          erro: { codigo: 'TOKEN_INVALIDO', mensagem: 'Sessao expirada.' },
        }),
      }),
    )

    await expect(request('/me')).rejects.toBeInstanceOf(ApiError)

    expect(window.localStorage.getItem('pokelab:sessao')).toBeNull()
  })

  it('traduz o envelope de erro do servidor para codigo e mensagem', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 409,
        json: async () => ({
          erro: { codigo: 'USUARIO_EM_USO', mensagem: 'Esse usuario ja existe.' },
        }),
      }),
    )

    const erro = await request('/auth/register').catch((motivo: unknown) => motivo)

    expect(erro).toBeInstanceOf(ApiError)
    expect((erro as ApiError).codigo).toBe('USUARIO_EM_USO')
    expect((erro as ApiError).message).toBe('Esse usuario ja existe.')
  })
})
