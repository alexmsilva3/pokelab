import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { sessaoExemplo } from '@/api/fixtures'

describe('store de sessao', () => {
  beforeEach(() => {
    vi.resetModules()
    window.localStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('guarda e le a sessao do localStorage', async () => {
    const store = await import('@/store/auth')
    store.guardarSessao(sessaoExemplo())
    expect(store.obterToken()).toBe('token-valido')
    expect(store.armazenamentoPersistente()).toBe(true)
  })

  it('limpar remove o token', async () => {
    const store = await import('@/store/auth')
    store.guardarSessao(sessaoExemplo())
    store.limparSessao()
    expect(store.obterToken()).toBeNull()
  })

  it('com storage bloqueado a sessao ainda vale nesta aba', async () => {
    // Sem o fallback em memoria, guardarSessao nao tinha efeito nenhum e o
    // professor voltava ao login logo apos entrar, em ciclo.
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('bloqueado')
    })

    const store = await import('@/store/auth')
    store.guardarSessao(sessaoExemplo({ token: 'token-em-memoria' }))

    expect(store.obterToken()).toBe('token-em-memoria')
    expect(store.armazenamentoPersistente()).toBe(false)
  })

  it('com storage bloqueado limpar a sessao continua funcionando', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('bloqueado')
    })

    const store = await import('@/store/auth')
    store.guardarSessao(sessaoExemplo())
    store.limparSessao()

    expect(store.obterToken()).toBeNull()
  })

  it('leitura que lanca nao derruba a aplicacao', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('bloqueado')
    })

    const store = await import('@/store/auth')
    expect(store.obterToken()).toBeNull()
  })
})
