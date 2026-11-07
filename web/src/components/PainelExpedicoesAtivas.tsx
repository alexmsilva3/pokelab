/**
 * Status das expedicoes em andamento, pensado para a tela do laboratorio
 * (pedido do professor: "e a tela principal, tem que mostrar o que esta em
 * campo"). Reusa o que `pages/Expedicoes.tsx` ja resolveu — `listarExpedicoes`
 * e `CartaoExpedicao` — em vez de reimplementar contador, receber relatorio
 * ou idempotencia de clique aqui: isso seria uma segunda fonte de verdade
 * para o tempo, exatamente o defeito que a revisao da Fase 6 pegou.
 *
 * Polling leve e so enquanto houver expedicao ativa, pausado com a aba
 * oculta e limpo no desmonte — o mesmo padrao de `pages/Expedicoes.tsx`,
 * porque esta tela ja consulta perfil e itens e nao deveria ganhar mais uma
 * fonte de requisicoes constantes.
 */
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { ESTADOS_ATIVOS, abortarExpedicao, listarExpedicoes } from '@/api/expedicoes'
import type { ExpedicaoResumo } from '@/api/tipos'
import { CartaoExpedicao } from '@/components/CartaoExpedicao'

const INTERVALO_POLL_MS = 5000

type Estado =
  | { tipo: 'carregando' }
  | { tipo: 'erro'; mensagem: string }
  | { tipo: 'pronto'; itens: ExpedicaoResumo[] }

export function PainelExpedicoesAtivas() {
  const [estado, setEstado] = useState<Estado>({ tipo: 'carregando' })
  const [abortandoId, setAbortandoId] = useState<string | null>(null)
  const [erroAbortar, setErroAbortar] = useState<string | null>(null)

  const carregar = useCallback(() => {
    setEstado({ tipo: 'carregando' })
    listarExpedicoes(ESTADOS_ATIVOS)
      .then((resposta) => setEstado({ tipo: 'pronto', itens: resposta.items }))
      .catch((motivo: unknown) => {
        const mensagem =
          motivo instanceof ApiError
            ? motivo.message
            : 'Nao foi possivel carregar as expedicoes em andamento. Verifique a conexao.'
        setEstado({ tipo: 'erro', mensagem })
      })
  }, [])

  // Atualizacao silenciosa: usada pelo polling e pelo aviso do contador ao
  // chegar a zero. Nao volta para "carregando" porque a lista ja tem dado
  // util na tela.
  const atualizarSilenciosamente = useCallback(() => {
    listarExpedicoes(ESTADOS_ATIVOS)
      .then((resposta) => setEstado({ tipo: 'pronto', itens: resposta.items }))
      .catch(() => {})
  }, [])

  useEffect(() => {
    carregar()
  }, [carregar])

  const quantidadeAtivas = estado.tipo === 'pronto' ? estado.itens.length : 0

  useEffect(() => {
    if (quantidadeAtivas === 0) return

    let intervaloId: number | undefined

    function parar() {
      if (intervaloId !== undefined) window.clearInterval(intervaloId)
      intervaloId = undefined
    }
    function iniciar() {
      parar()
      intervaloId = window.setInterval(atualizarSilenciosamente, INTERVALO_POLL_MS)
    }
    function aoMudarVisibilidade() {
      if (document.visibilityState === 'visible') {
        atualizarSilenciosamente()
        iniciar()
      } else {
        parar()
      }
    }

    if (document.visibilityState === 'visible') iniciar()
    document.addEventListener('visibilitychange', aoMudarVisibilidade)

    return () => {
      parar()
      document.removeEventListener('visibilitychange', aoMudarVisibilidade)
    }
  }, [quantidadeAtivas, atualizarSilenciosamente])

  async function abortar(id: string) {
    const confirmado = window.confirm(
      'Abortar esta expedicao? O treinador volta agora, mas os itens levados nao retornam.',
    )
    if (!confirmado) return

    setErroAbortar(null)
    setAbortandoId(id)
    try {
      await abortarExpedicao(id)
      atualizarSilenciosamente()
    } catch (motivo) {
      setErroAbortar(
        motivo instanceof ApiError ? motivo.message : 'Nao foi possivel abortar a expedicao.',
      )
    } finally {
      setAbortandoId(null)
    }
  }

  return (
    <section className="secao-expedicoes-ativas" aria-label="Expedicoes em andamento">
      <h2>Expedicoes em andamento</h2>

      {estado.tipo === 'carregando' && <p>Carregando expedicoes...</p>}

      {estado.tipo === 'erro' && (
        <div>
          <p role="alert" className="mensagem-erro">
            {estado.mensagem}
          </p>
          <button type="button" onClick={carregar}>
            Tentar novamente
          </button>
        </div>
      )}

      {estado.tipo === 'pronto' &&
        (estado.itens.length === 0 ? (
          <p className="aviso-vazio">
            Nenhuma expedicao em andamento. <Link to="/expedicoes">Despache um treinador</Link>{' '}
            para comecar.
          </p>
        ) : (
          <>
            {erroAbortar && (
              <p role="alert" className="mensagem-erro">
                {erroAbortar}
              </p>
            )}
            <ul className="lista-expedicoes">
              {estado.itens.map((expedicao) => (
                <li key={expedicao.id}>
                  <CartaoExpedicao
                    expedicao={expedicao}
                    abortando={abortandoId === expedicao.id}
                    onAbortar={() => abortar(expedicao.id)}
                    onChegarAZero={atualizarSilenciosamente}
                    onAtualizar={atualizarSilenciosamente}
                  />
                </li>
              ))}
            </ul>
          </>
        ))}
    </section>
  )
}
