/**
 * Sessao do professor. Sem biblioteca de estado global: tres campos (token,
 * professor, laboratorio) guardados juntos.
 *
 * O destino preferido e localStorage, mas ele pode falhar — modo privado
 * restrito, politica de cookies, cota estourada. Antes, a falha era engolida
 * em silencio e a sessao simplesmente nao existia: o professor entrava, era
 * devolvido ao login, entrava de novo, para sempre, sem nenhuma mensagem.
 *
 * Por isso ha um fallback em memoria. Com storage bloqueado a sessao nao
 * sobrevive a recarregar a pagina, mas a aba atual funciona, e
 * `armazenamentoPersistente()` permite avisar a pessoa em vez de deixa-la
 * descobrir sozinha.
 */
import { useSyncExternalStore } from 'react'
import type { Sessao } from '@/api/tipos'

const CHAVE_SESSAO = 'pokelab:sessao'

const ouvintes = new Set<() => void>()

/** Vira false na primeira escrita que o navegador recusar. */
let persistente = true
/** Usado quando o localStorage nao aceita gravar. */
let sessaoEmMemoria: string | null = null

function notificar() {
  ouvintes.forEach((ouvinte) => ouvinte())
}

function inscrever(ouvinte: () => void) {
  ouvintes.add(ouvinte)
  return () => ouvintes.delete(ouvinte)
}

function lerArmazenamento(): string | null {
  if (!persistente) {
    return sessaoEmMemoria
  }
  try {
    return window.localStorage.getItem(CHAVE_SESSAO)
  } catch {
    persistente = false
    return sessaoEmMemoria
  }
}

function escreverArmazenamento(valor: string): void {
  sessaoEmMemoria = valor
  try {
    window.localStorage.setItem(CHAVE_SESSAO, valor)
  } catch {
    persistente = false
  }
}

function removerArmazenamento(): void {
  sessaoEmMemoria = null
  try {
    window.localStorage.removeItem(CHAVE_SESSAO)
  } catch {
    persistente = false
  }
}

// useSyncExternalStore exige que getSnapshot devolva a mesma referencia
// quando nada mudou, senao React entende que ha uma atualizacao a cada
// leitura e entra em loop. Por isso o parse so acontece quando a string
// bruta muda.
let cacheBruto: string | null = null
let cacheSessao: Sessao | null = null

function lerSessao(): Sessao | null {
  const bruto = lerArmazenamento()
  if (bruto === cacheBruto) {
    return cacheSessao
  }

  cacheBruto = bruto
  if (!bruto) {
    cacheSessao = null
    return null
  }

  try {
    cacheSessao = JSON.parse(bruto) as Sessao
  } catch {
    cacheSessao = null
  }
  return cacheSessao
}

/** Le o token atual de forma sincrona, para uso fora de componentes React. */
export function obterToken(): string | null {
  return lerSessao()?.token ?? null
}

/**
 * false quando o navegador recusou gravar: a sessao vale so para esta aba e
 * se perde ao recarregar. A interface deve avisar.
 */
export function armazenamentoPersistente(): boolean {
  return persistente
}

export function guardarSessao(sessao: Sessao): void {
  escreverArmazenamento(JSON.stringify(sessao))
  notificar()
}

export function limparSessao(): void {
  removerArmazenamento()
  notificar()
}

/** Hook reativo: re-renderiza quando a sessao muda em qualquer lugar da aplicacao. */
export function useSessao(): Sessao | null {
  return useSyncExternalStore(inscrever, lerSessao, () => null)
}
