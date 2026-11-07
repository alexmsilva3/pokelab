/**
 * Tela de relatorio de campo (spec 007, criterio 19): o pagamento do jogo.
 * Alcancada do painel de expedicoes quando o professor clica "Receber
 * relatorio" ou "Ver relatorio" (`components/CartaoExpedicao.tsx`).
 *
 * "Receber relatorio" chega aqui com a `ExpedicaoLer` que o proprio claim
 * devolveu no `state` da navegacao (ADR-006): o corpo do `POST .../claim` ja
 * tem o relatorio dentro, e refazer um `GET` so para reler o que acabou de
 * chegar seria buscar o mesmo relatorio duas vezes no servidor por um
 * clique. "Ver relatorio" (estado terminal sem claim nesta sessao) e a
 * entrada direta por URL chegam sem esse `state`, e so ai a tela faz o
 * `GET /expeditions/{id}` puro — nunca chama o claim daqui. Isso faz desta
 * tela algo que o professor pode reabrir, atualizar ou favoritar sem efeito
 * colateral nenhum, e o relatorio nulo (expedicao ainda nao resolvida, ou
 * abortada antes de gerar relatorio) e um estado normal, nao um erro.
 *
 * Ordem da tela (nao cronologica): resultado em uma linha, capturas, as tres
 * experiencias, itens, e so por ultimo a linha do tempo completa — o
 * professor quer saber primeiro o que trouxe, nao a historia inteira.
 */
import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { buscarExpedicao } from '@/api/expedicoes'
import type { ExpedicaoLer, RelatorioDeCampo as RelatorioDeCampoTipo } from '@/api/tipos'
import { CapturasDoRelatorio } from '@/components/CapturasDoRelatorio'
import { ExperienciasDoRelatorio } from '@/components/ExperienciasDoRelatorio'
import { ItensDoRelatorio } from '@/components/ItensDoRelatorio'
import { Timeline } from '@/components/Timeline'
import { rotuloStatusRelatorio } from '@/lib/relatorios'

type Estado =
  | { tipo: 'carregando' }
  | { tipo: 'erro'; mensagem: string }
  | { tipo: 'pronto'; expedicao: ExpedicaoLer }

interface EstadoDeNavegacao {
  expedicao?: ExpedicaoLer
}

export function RelatorioDeCampo() {
  const { id } = useParams<{ id: string }>()
  const location = useLocation()
  const precarregada = (location.state as EstadoDeNavegacao | null)?.expedicao
  const expedicaoPrecarregada = precarregada && precarregada.id === id ? precarregada : null

  const [estado, setEstado] = useState<Estado>(
    expedicaoPrecarregada
      ? { tipo: 'pronto', expedicao: expedicaoPrecarregada }
      : { tipo: 'carregando' },
  )

  const carregar = useCallback(() => {
    if (!id) return
    setEstado({ tipo: 'carregando' })
    buscarExpedicao(id)
      .then((expedicao) => setEstado({ tipo: 'pronto', expedicao }))
      .catch((motivo: unknown) => {
        const mensagem =
          motivo instanceof ApiError
            ? motivo.message
            : 'Nao foi possivel carregar o relatorio. Verifique a conexao.'
        setEstado({ tipo: 'erro', mensagem })
      })
  }, [id])

  useEffect(() => {
    // A expedicao ja chegou pronta do claim (ver doc do arquivo): nada para
    // buscar. So entra em "carregando" quando a tela foi aberta sem esse
    // `state` — "Ver relatorio", recarga de pagina ou URL direta.
    if (expedicaoPrecarregada) return
    carregar()
  }, [carregar, expedicaoPrecarregada])

  return (
    <main className="tela-relatorio">
      <header>
        <h1>Relatorio de campo</h1>
        <Link to="/expedicoes">Voltar as expedicoes</Link>
      </header>

      {estado.tipo === 'carregando' && <p>Carregando relatorio...</p>}

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
        (estado.expedicao.relatorio === null ? (
          <p className="aviso-vazio">
            {estado.expedicao.status === 'ABORTADA'
              ? 'Esta expedicao foi abortada antes de gerar relatorio.'
              : 'O relatorio ainda nao esta pronto. Volte ao painel de expedicoes e receba-o por la.'}
          </p>
        ) : (
          <ConteudoRelatorio expedicao={estado.expedicao} relatorio={estado.expedicao.relatorio} />
        ))}
    </main>
  )
}

function ConteudoRelatorio({
  expedicao,
  relatorio,
}: {
  expedicao: ExpedicaoLer
  relatorio: RelatorioDeCampoTipo
}) {
  const sucesso = relatorio.status === 'CONCLUIDA_SUCESSO'

  return (
    <div className="relatorio-corpo">
      <section aria-label="Resultado">
        <p
          className={
            sucesso
              ? 'relatorio-resultado relatorio-resultado-sucesso'
              : 'relatorio-resultado relatorio-resultado-falha'
          }
        >
          <strong>{rotuloStatusRelatorio(relatorio.status)}.</strong>{' '}
          {expedicao.treinador_nome} voltou de {expedicao.local_destino_nome}.
          {relatorio.local_desbloqueado && ' O local foi desbloqueado.'}
        </p>
      </section>

      {/*
        As tres listas curtas dividem a linha em tela larga e empilham em tela
        estreita, sem media query — `auto-fit` com `minmax` resolve. Cada uma
        continua sendo uma <section> com rotulo proprio: o agrupamento e
        visual, e a navegacao por regiao do leitor de tela nao muda.
      */}
      <div className="relatorio-blocos">
        <section aria-label="Capturas">
          <h2>Capturas</h2>
          <CapturasDoRelatorio capturas={relatorio.capturas} />
        </section>

        <section aria-label="Experiencia ganha">
          <h2>Experiencia</h2>
          <ExperienciasDoRelatorio
            time={relatorio.time}
            treinador={relatorio.treinador}
            laboratorio={relatorio.laboratorio}
          />
        </section>

        <section aria-label="Itens">
          <h2>Itens</h2>
          <ItensDoRelatorio
            consumidos={relatorio.itens_consumidos}
            encontrados={relatorio.itens_encontrados}
          />
        </section>
      </div>

      {/* A linha do tempo fica em largura cheia: e a unica lista que cresce. */}
      <section aria-label="Linha do tempo" className="relatorio-linha-do-tempo">
        <h2>Linha do tempo</h2>
        <Timeline eventos={relatorio.eventos} />
      </section>
    </div>
  )
}
