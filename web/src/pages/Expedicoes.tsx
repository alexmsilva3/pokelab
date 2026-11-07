/**
 * Painel de expedicoes (spec 006, tarefas 9 e 10; historico, spec 007):
 * despacho, acompanhamento das ativas e o historico do que ja terminou.
 * Polling leve — so enquanto houver expedicao ativa, pausado quando a aba
 * esta oculta (document.visibilityState) — e sempre corrigido pelo que o
 * servidor manda a cada leitura (Artigo II).
 *
 * Sem a secao de historico, uma expedicao some do painel no instante em que
 * o professor acaba de receber o relatorio dela: `CartaoExpedicao.tsx` ja
 * sabe desenhar "Ver relatorio" para o estado terminal, mas nada aqui pedia
 * essas expedicoes de volta. O historico consulta os tres estados terminais
 * e reusa o mesmo cartao.
 */
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { ESTADOS_ATIVOS, ESTADOS_HISTORICO, abortarExpedicao, listarExpedicoes } from '@/api/expedicoes'
import type { ExpedicaoResumo } from '@/api/tipos'
import { CartaoExpedicao } from '@/components/CartaoExpedicao'
import { DespacharExpedicao } from '@/components/DespacharExpedicao'
import { JANELA_HISTORICO, LIMITE_HISTORICO, maisRecentes } from '@/lib/expedicoes'

/** So custa uma requisicao leve e so roda com a aba visivel; nao e tempo de jogo. */
const INTERVALO_POLL_MS = 5000

type Estado =
  | { tipo: 'carregando' }
  | { tipo: 'erro'; mensagem: string }
  | { tipo: 'pronto'; itens: ExpedicaoResumo[] }

export function Expedicoes() {
  const [estado, setEstado] = useState<Estado>({ tipo: 'carregando' })
  const [estadoHistorico, setEstadoHistorico] = useState<Estado>({ tipo: 'carregando' })
  const [abortandoId, setAbortandoId] = useState<string | null>(null)
  const [erroAbortar, setErroAbortar] = useState<string | null>(null)

  /**
   * O historico so desenha cartoes em estado terminal: `CartaoExpedicao`
   * nunca chama contador, claim nem abortar para esses casos, entao os
   * callbacks correspondentes nunca disparam aqui — ficam so para satisfazer
   * a mesma prop de sempre.
   */
  const semEfeito = useCallback(() => {}, [])

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

  const carregarHistorico = useCallback(() => {
    setEstadoHistorico({ tipo: 'carregando' })
    // `limite` (Achado 1, revisao da Fase 7): pede ao servidor uma janela
    // ja pequena em vez de baixar o historico inteiro so para desenhar
    // `LIMITE_HISTORICO` cartoes — ver `lib/expedicoes.ts::JANELA_HISTORICO`.
    listarExpedicoes(ESTADOS_HISTORICO, { limite: JANELA_HISTORICO })
      .then((resposta) => setEstadoHistorico({ tipo: 'pronto', itens: resposta.items }))
      .catch((motivo: unknown) => {
        const mensagem =
          motivo instanceof ApiError
            ? motivo.message
            : 'Nao foi possivel carregar o historico. Verifique a conexao.'
        setEstadoHistorico({ tipo: 'erro', mensagem })
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
    carregarHistorico()
  }, [carregar, carregarHistorico])

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
      // A expedicao abortada acabou de virar historico: sem isso ela some do
      // painel de ativas e so reaparece se o professor recarregar a tela.
      carregarHistorico()
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
                      onAtualizar={atualizarSilenciosamente}
                    />
                  </li>
                ))}
              </ul>
            </>
          ))}
      </section>

      <section aria-label="Historico de expedicoes">
        <h2>Historico</h2>
        <p className="legenda-secao">As {LIMITE_HISTORICO} mais recentes.</p>

        {estadoHistorico.tipo === 'carregando' && <p>Carregando historico...</p>}

        {estadoHistorico.tipo === 'erro' && (
          <div>
            <p role="alert" className="mensagem-erro">
              {estadoHistorico.mensagem}
            </p>
            <button type="button" onClick={carregarHistorico}>
              Tentar novamente
            </button>
          </div>
        )}

        {estadoHistorico.tipo === 'pronto' &&
          (estadoHistorico.itens.length === 0 ? (
            <p className="aviso-vazio">
              Nenhuma expedicao concluida ainda. O historico aparece aqui assim que a primeira
              terminar.
            </p>
          ) : (
            <ul className="lista-expedicoes">
              {maisRecentes(estadoHistorico.itens, LIMITE_HISTORICO).map((expedicao) => (
                <li key={expedicao.id}>
                  <CartaoExpedicao
                    expedicao={expedicao}
                    abortando={false}
                    onAbortar={semEfeito}
                    onChegarAZero={semEfeito}
                    onAtualizar={semEfeito}
                  />
                </li>
              ))}
            </ul>
          ))}
      </section>
    </main>
  )
}
