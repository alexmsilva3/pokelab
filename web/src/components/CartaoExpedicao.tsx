/**
 * Cartao de uma expedicao no painel (spec 006, extraido de `pages/Expedicoes.tsx`
 * quando a spec 007 deu a ele um segundo botao). O que o cartao mostra depende
 * so do `estado_observado` que o servidor manda, nunca do relogio local
 * (Artigo II):
 *
 * - `AGUARDANDO_RELATORIO`: acao primaria "Receber relatorio", que chama
 *   `POST /expeditions/{id}/claim` (ADR-006) e so entao navega para a tela do
 *   relatorio, levando a `ExpedicaoLer` que o claim devolveu no `state` da
 *   navegacao — o relatorio ja chegou neste corpo, e `RelatorioDeCampo.tsx`
 *   nao precisa refazer o `GET` que o claim acabou de responder. Dois
 *   cliques nao disparam duas chamadas — a trava e uma `ref`, porque o
 *   estado do React so atualiza no proximo render e dois cliques sincronos
 *   (como os de um teste com `fireEvent`) ainda veriam o botao habilitado no
 *   primeiro clique.
 * - Estado terminal (`CONCLUIDA_SUCESSO`, `CONCLUIDA_FALHA`, `ABORTADA`):
 *   "Ver relatorio", que so navega — o relatorio ja existe ou nunca vai
 *   existir (expedicao abortada), e a propria tela do relatorio decide o que
 *   mostrar.
 *
 * Se o servidor recusar o claim com `EXPEDICAO_EM_CURSO`, a mensagem exibida
 * e a DELE, nao uma reescrita: significa que o contador local da tela
 * adiantou e o prazo ainda nao venceu de verdade. O cartao tambem pede ao
 * painel para reconsultar a lista, para mostrar o estado real.
 */
import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { receberRelatorio } from '@/api/expedicoes'
import type { ExpedicaoResumo } from '@/api/tipos'
import { ContadorRegressivo } from '@/components/ContadorRegressivo'
import { rotuloEstadoObservado } from '@/lib/expedicoes'

export interface CartaoExpedicaoProps {
  /**
   * `ExpedicaoResumo` (revisao da Fase 7, achado 1): o cartao nunca le
   * `relatorio` diretamente — so navega para a tela do relatorio, que busca
   * o conteudo por conta propria (`GET /expeditions/{id}` ou o claim) — e
   * por isso aceita tanto a linha da listagem quanto a ficha completa
   * (`ExpedicaoLer`), que e um `ExpedicaoResumo` com um campo a mais.
   */
  expedicao: ExpedicaoResumo
  abortando: boolean
  onAbortar: () => void
  onChegarAZero: () => void
  /** Chamado apos o claim recusar ou falhar, para o painel reconsultar a lista. */
  onAtualizar: () => void
}

const ESTADOS_TERMINAIS = new Set(['CONCLUIDA_SUCESSO', 'CONCLUIDA_FALHA', 'ABORTADA'])

export function CartaoExpedicao({
  expedicao,
  abortando,
  onAbortar,
  onChegarAZero,
  onAtualizar,
}: CartaoExpedicaoProps) {
  const navigate = useNavigate()
  const [recebendo, setRecebendo] = useState(false)
  const [erroReceber, setErroReceber] = useState<string | null>(null)
  const emVooRef = useRef(false)

  // Abortar e exclusivo do EM_CURSO, e a regra e do SERVIDOR:
  // `services/expedicoes.abortar` recusa com 409 qualquer estado observado que
  // nao seja EM_CURSO — AGUARDANDO_RELATORIO inclusive, porque a expedicao ja
  // terminou e o que falta e colher o resultado, nao cancela-lo.
  //
  // Este comentario antes afirmava o contrario, e o botao seguia a afirmacao:
  // vencido o prazo, "Abortar" continuava habilitado e o clique levava 409.
  // Note a forma da condicao abaixo: o botao aparece para o UNICO estado que
  // aceita a operacao, nao para todos menos os terminais. Enumerar quem pode e
  // mais seguro que enumerar quem nao pode — um estado novo nasce sem permissao
  // em vez de nascer com ela.
  const emCurso = expedicao.estado_observado === 'EM_CURSO'
  const aguardandoRelatorio = expedicao.estado_observado === 'AGUARDANDO_RELATORIO'
  const terminal = ESTADOS_TERMINAIS.has(expedicao.estado_observado)

  async function aoReceberRelatorio() {
    if (emVooRef.current) return
    emVooRef.current = true
    setRecebendo(true)
    setErroReceber(null)
    try {
      const resposta = await receberRelatorio(expedicao.id)
      // O corpo do claim ja traz a expedicao com o relatorio dentro
      // (ExpedicaoClaimLer, plan.md): leva ela na navegacao para
      // `RelatorioDeCampo.tsx` nao refazer um `GET` que acabou de responder.
      navigate(`/expedicoes/${expedicao.id}/relatorio`, {
        state: { expedicao: resposta.expedicao },
      })
    } catch (motivo) {
      setErroReceber(
        motivo instanceof ApiError
          ? motivo.message
          : 'Nao foi possivel receber o relatorio. Tente novamente.',
      )
      onAtualizar()
    } finally {
      emVooRef.current = false
      setRecebendo(false)
    }
  }

  function aoVerRelatorio() {
    navigate(`/expedicoes/${expedicao.id}/relatorio`)
  }

  return (
    <article className="cartao-expedicao" aria-label={`Expedicao de ${expedicao.treinador_nome}`}>
      <h3>{expedicao.treinador_nome}</h3>
      <p className="cartao-expedicao-destino">Destino: {expedicao.local_destino_nome}</p>
      <span className="rotulo">{rotuloEstadoObservado(expedicao.estado_observado)}</span>

      {/*
        `segundos_restantes` so e nulo em estado terminal (schemas/expedicoes.py):
        a guarda dupla documenta isso para o compilador sem fingir que o
        servidor manda um numero inventado para uma expedicao ja encerrada.
      */}
      {emCurso && expedicao.segundos_restantes !== null && (
        <p className="cartao-expedicao-tempo">
          Tempo restante:{' '}
          <ContadorRegressivo
            segundosRestantes={expedicao.segundos_restantes}
            aoChegarAZero={onChegarAZero}
          />
        </p>
      )}

      {erroReceber && (
        <p role="alert" className="mensagem-erro">
          {erroReceber}
        </p>
      )}

      {aguardandoRelatorio && (
        <button
          type="button"
          className="botao-primario"
          disabled={recebendo}
          onClick={aoReceberRelatorio}
        >
          {recebendo ? 'Recebendo...' : 'Receber relatorio'}
        </button>
      )}

      {terminal && (
        <button type="button" onClick={aoVerRelatorio}>
          Ver relatorio
        </button>
      )}

      {emCurso && (
        <button type="button" disabled={abortando} onClick={onAbortar}>
          {abortando ? 'Abortando...' : 'Abortar'}
        </button>
      )}
    </article>
  )
}
