/**
 * Cliente HTTP do PokeLab.
 *
 * Artigo II da constituicao: o cliente desenha o que a API devolve e nunca
 * calcula resultado, duracao restante ou probabilidade por conta propria.
 *
 * Na Fase 2 este arquivo passa a ser gerado a partir do OpenAPI da API.
 */
import { limparSessao, obterToken } from '@/store/auth'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

/**
 * Monta a URL de um sprite a partir do caminho relativo que o servidor manda
 * (ex.: "25-front.png"). O acervo de imagens e servido pela propria API
 * (Artigo V: nenhuma requisicao a servico externo), nunca montado a partir
 * de um host fixo no banco.
 */
export function urlSprite(caminho: string): string {
  return `${BASE_URL}/sprites/${caminho}`
}

/**
 * Erro de API traduzido do envelope do servidor
 * ({"erro": {"codigo", "mensagem", "detalhes"}}) para algo que a tela usa
 * diretamente: a mensagem em `message` ja vem em portugues, escrita pelo
 * servidor, e `codigo` permite distinguir casos sem comparar texto.
 */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly codigo: string | null,
    mensagem: string,
  ) {
    super(mensagem)
    this.name = 'ApiError'
  }
}

interface EnvelopeErro {
  erro?: {
    codigo?: string
    mensagem?: string
    detalhes?: unknown
  }
  /** Formato cru do FastAPI, caso alguma rota escape do envelope da aplicacao. */
  detail?: unknown
}

/**
 * Mensagem de ultimo recurso, por faixa de status.
 *
 * `response.statusText` e texto de protocolo em ingles ("Unprocessable
 * Entity"), e o Artigo X nao abre excecao para mensagem de erro.
 */
function mensagemPadrao(status: number): string {
  if (status === 401) return 'Sua sessao expirou. Entre novamente.'
  if (status === 403) return 'Voce nao tem permissao para esta acao.'
  if (status === 404) return 'Nao encontramos o que voce procura.'
  if (status === 409) return 'Esta acao conflita com o estado atual do laboratorio.'
  if (status === 422) return 'Os dados enviados nao sao validos. Confira os campos.'
  if (status >= 500) return 'O servidor falhou. Tente de novo em instantes.'
  return 'Nao foi possivel completar a acao.'
}

async function construirErro(response: Response): Promise<ApiError> {
  let corpo: EnvelopeErro | null = null
  try {
    corpo = (await response.json()) as EnvelopeErro
  } catch {
    corpo = null
  }

  const codigo = corpo?.erro?.codigo ?? null
  const mensagem = corpo?.erro?.mensagem?.trim() || mensagemPadrao(response.status)
  return new ApiError(response.status, codigo, mensagem)
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = obterToken()

  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  })

  if (!response.ok) {
    const erro = await construirErro(response)

    // Token expirado ou invalido numa chamada autenticada: a sessao nao
    // serve mais. Limpa e manda para o login em vez de deixar a tela num
    // estado quebrado ou num loop de erro repetido a cada poll.
    if (response.status === 401 && token) {
      limparSessao()
      if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
        window.location.assign('/login')
      }
    }

    throw erro
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}
