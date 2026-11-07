/**
 * Tela do viveiro (spec 008, tarefa 16): ocupacao e capacidade, a lista do
 * que esta guardado, e o soltar com confirmacao nomeando quem vai embora.
 *
 * O TRANSBORDO (plan.md, "O transbordo"): quando `transbordado` e verdadeiro,
 * a unica porta que fecha e o despacho de expedicao nova — reclamar
 * relatorio, aceitar entrega, concluir entrega e soltar continuam
 * funcionando (regra 4). Esta tela existe para que o professor NUNCA fique
 * preso sem entender por que: o aviso diz quantos lugares faltam e as DUAS
 * saidas possiveis — soltar aqui mesmo, ou entregar na Central.
 */
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '@/api/client'
import type { PokemonResumo, Viveiro as ViveiroResposta } from '@/api/tipos'
import { buscarViveiro, soltarPokemon } from '@/api/viveiro'
import { CartaoPokemonViveiro } from '@/components/CartaoPokemonViveiro'

type Estado =
  | { tipo: 'carregando' }
  | { tipo: 'erro'; mensagem: string }
  | { tipo: 'pronto'; viveiro: ViveiroResposta }

export function Viveiro() {
  const [estado, setEstado] = useState<Estado>({ tipo: 'carregando' })
  const [soltandoId, setSoltandoId] = useState<string | null>(null)
  const [erroSoltar, setErroSoltar] = useState<string | null>(null)

  const carregar = useCallback((sinal?: AbortSignal) => {
    setEstado({ tipo: 'carregando' })
    buscarViveiro(sinal)
      .then((viveiro) => setEstado({ tipo: 'pronto', viveiro }))
      .catch((motivo: unknown) => {
        if (motivo instanceof DOMException && motivo.name === 'AbortError') return
        const mensagem =
          motivo instanceof ApiError
            ? motivo.message
            : 'Nao foi possivel carregar o viveiro. Verifique a conexao.'
        setEstado({ tipo: 'erro', mensagem })
      })
  }, [])

  useEffect(() => {
    const controlador = new AbortController()
    carregar(controlador.signal)
    return () => controlador.abort()
  }, [carregar])

  async function soltar(pokemon: PokemonResumo) {
    const confirmado = window.confirm(
      `Soltar ${pokemon.nome} (Nv. ${pokemon.nivel})? Ele volta a natureza, nao rende nada, e esta acao nao pode ser desfeita.`,
    )
    if (!confirmado) return

    setErroSoltar(null)
    setSoltandoId(pokemon.id)
    try {
      await soltarPokemon(pokemon.id)
      carregar()
    } catch (motivo) {
      setErroSoltar(
        motivo instanceof ApiError ? motivo.message : 'Nao foi possivel soltar este Pokemon.',
      )
    } finally {
      setSoltandoId(null)
    }
  }

  if (estado.tipo === 'carregando') {
    return (
      <main className="tela-viveiro">
        <p>Carregando viveiro...</p>
      </main>
    )
  }

  if (estado.tipo === 'erro') {
    return (
      <main className="tela-viveiro">
        <p role="alert" className="mensagem-erro">
          {estado.mensagem}
        </p>
        <button type="button" onClick={() => carregar()}>
          Tentar novamente
        </button>
      </main>
    )
  }

  const { viveiro } = estado

  return (
    <main className="tela-viveiro">
      <header>
        <h1>Viveiro</h1>
        <Link to="/laboratorio">Voltar ao laboratorio</Link>
      </header>

      <dl className="viveiro-resumo" aria-label="Ocupacao do viveiro">
        <div>
          <dt>Ocupacao</dt>
          <dd>
            {viveiro.ocupacao} / {viveiro.capacidade}
          </dd>
        </div>
      </dl>

      {viveiro.transbordado && (
        <div role="alert" className="viveiro-aviso-transbordo">
          <p>
            O viveiro transbordou: faltam {viveiro.lugares_faltando}{' '}
            {viveiro.lugares_faltando === 1 ? 'lugar' : 'lugares'}. Nenhuma expedicao nova pode
            partir ate caber.
          </p>
          <p>
            Para voltar a despachar, solte Pokemon na lista abaixo ou{' '}
            <Link to="/entregas">entregue-os na Central de Entregas</Link>.
          </p>
        </div>
      )}

      {erroSoltar && (
        <p role="alert" className="mensagem-erro">
          {erroSoltar}
        </p>
      )}

      {viveiro.items.length === 0 ? (
        <p className="aviso-vazio">
          Nenhum Pokemon no viveiro agora. Eles estao todos em time ou em expedicao — volte apos
          uma captura para ve-los aqui.
        </p>
      ) : (
        <ul className="lista-viveiro" aria-label="Pokemon no viveiro">
          {viveiro.items.map((pokemon) => (
            <li key={pokemon.id}>
              <CartaoPokemonViveiro
                pokemon={pokemon}
                soltando={soltandoId === pokemon.id}
                onSoltar={() => soltar(pokemon)}
              />
            </li>
          ))}
        </ul>
      )}
    </main>
  )
}
