/**
 * Cliente HTTP do PokeLab.
 *
 * Artigo II da constituicao: o cliente desenha o que a API devolve e nunca
 * calcula resultado, duracao restante ou probabilidade por conta propria.
 *
 * Na Fase 2 este arquivo passa a ser gerado a partir do OpenAPI da API.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  })

  if (!response.ok) {
    const corpo = await response.text()
    throw new ApiError(response.status, corpo || response.statusText)
  }

  return response.json() as Promise<T>
}

export interface Health {
  status: string
}

export const verificarSaude = () => request<Health>('/health')
