/**
 * Painel de expedicoes (spec 006, tarefas 9 e 10): despacho e acompanhamento
 * das ativas. Polling leve — so enquanto houver expedicao ativa, pausado
 * quando a aba esta oculta (document.visibilityState) — e sempre corrigido
 * pelo que o servidor manda a cada leitura (Artigo II).
 */
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { ESTADOS_ATIVOS, abortarExpedicao, listarExpedicoes } from '@/api/expedicoes'
import type { ExpedicaoLer } from '@/api/tipos'
import { ContadorRegressivo } from '@/components/ContadorRegressivo'
import { DespacharExpedicao } from '@/components/DespacharExpedicao'
import { rotuloEstadoObservado } from '@/lib/expedicoes'

/** So custa uma requisicao leve e so roda com a aba visivel; nao e tempo de jogo. */
const INTERVALO_POLL_MS = 5000

type Estado =
  | { tipo: 'carregando' }
  | { tipo: 'erro'; mensagem: string }
  | { tipo: 'pronto'; itens: ExpedicaoLer[] }

export function Expedicoes() {
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
            : 'Nao foi possivel carregar as expedicoes. Verifique a conexao.'
        setEstado({ tipo: 'erro', mensagem })
      })
  }, [])

  /**
   * Atualizacao silenciosa: usada pelo polling e pelo aviso do contador ao
   * chegar a zero. Nao volta para "carregando" (a lista ja tem dado util na
   * tela) e uma falha aqui nao vira erro de tela inteira — a proxima
   * tentativa, poll ou acao do professor, tenta de novo.
   */
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
    <main className="tela-expedicoes">
      <header>
        <h1>Expedicoes</h1>
        <Link to="/laboratorio">Voltar ao laboratorio</Link>
      </header>

      <DespacharExpedicao onDespachado={() => carregar()} />

      <section aria-label="Expedicoes ativas">
        <h2>Ativas</h2>

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
              Nenhuma expedicao em curso. Despache um treinador acima para comecar.
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
                    />
                  </li>
                ))}
              </ul>
            </>
          ))}
      </section>
    </main>
  )
}

function CartaoExpedicao({
  expedicao,
  abortando,
  onAbortar,
  onChegarAZero,
}: {
  expedicao: ExpedicaoLer
  abortando: boolean
  onAbortar: () => void
  onChegarAZero: () => void
}) {
  // A lista ja chega filtrada por `status=EM_CURSO` (a coluna crua, nao o
  // estado observado): toda expedicao aqui ainda pode ser abortada, mesmo a
  // que ja esta AGUARDANDO_RELATORIO — so o contador deixa de fazer sentido
  // quando o prazo ja passou, por isso ele e exclusivo do EM_CURSO.
  const emCurso = expedicao.estado_observado === 'EM_CURSO'

  return (
    <article className="cartao-expedicao" aria-label={`Expedicao de ${expedicao.treinador_nome}`}>
      <h3>{expedicao.treinador_nome}</h3>
      <p className="cartao-expedicao-destino">Destino: {expedicao.local_destino_nome}</p>
      <span className="rotulo">{rotuloEstadoObservado(expedicao.estado_observado)}</span>

      {emCurso && (
        <p className="cartao-expedicao-tempo">
          Tempo restante:{' '}
          <ContadorRegressivo
            segundosRestantes={expedicao.segundos_restantes}
            aoChegarAZero={onChegarAZero}
          />
        </p>
      )}

      <button type="button" disabled={abortando} onClick={onAbortar}>
        {abortando ? 'Abortando...' : 'Abortar'}
      </button>
    </article>
  )
}
