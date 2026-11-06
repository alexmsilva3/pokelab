/**
 * Formulario de despacho (spec 006, tarefa 9). Escolhe treinador, destino e
 * carga; a previa chama POST /expeditions/preview a cada mudanca, cancelando
 * a chamada anterior (uma resposta antiga chegando depois da nova mostraria
 * numero de outra composicao). Duracao, dificuldade e chance de sucesso vem
 * prontas do servidor (Artigo II) — o componente nunca calcula nenhuma delas.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { despacharExpedicao, previsualizarExpedicao } from '@/api/expedicoes'
import { buscarMapa } from '@/api/mapa'
import { listarItens } from '@/api/itens'
import { listarTreinadores } from '@/api/trainers'
import type {
  ExpedicaoLer,
  ItemCargaEntrada,
  ItemEmEstoque,
  LocalNoMapa,
  PreviaExpedicao,
  TreinadorResumo,
} from '@/api/tipos'
import { formatarPercentual } from '@/lib/expedicoes'
import { rotuloEstadoLocal } from '@/lib/mapa'
import { rotuloStatus } from '@/lib/treinadores'

export interface DespacharExpedicaoProps {
  /** Chamado com a expedicao recem-criada, para o pai atualizar a lista de ativas. */
  onDespachado: (expedicao: ExpedicaoLer) => void
}

interface DadosApoio {
  treinadores: TreinadorResumo[]
  locais: LocalNoMapa[]
  itens: ItemEmEstoque[]
}

type EstadoApoio =
  | { tipo: 'carregando' }
  | { tipo: 'erro'; mensagem: string }
  | { tipo: 'pronto'; dados: DadosApoio }

type EstadoPrevia =
  | { tipo: 'incompleto' }
  | { tipo: 'carregando' }
  | { tipo: 'erro'; mensagem: string }
  | { tipo: 'pronto'; previa: PreviaExpedicao }

function carregaParaEntrada(carga: Record<string, number>): ItemCargaEntrada[] {
  return Object.entries(carga)
    .filter(([, quantidade]) => quantidade > 0)
    .map(([item_id, quantidade]) => ({ item_id, quantidade }))
}

export function DespacharExpedicao({ onDespachado }: DespacharExpedicaoProps) {
  const [estadoApoio, setEstadoApoio] = useState<EstadoApoio>({ tipo: 'carregando' })
  const [treinadorId, setTreinadorId] = useState('')
  const [localId, setLocalId] = useState('')
  const [carga, setCarga] = useState<Record<string, number>>({})
  const [estadoPrevia, setEstadoPrevia] = useState<EstadoPrevia>({ tipo: 'incompleto' })
  const [despachando, setDespachando] = useState(false)
  const [erroDespacho, setErroDespacho] = useState<string | null>(null)
  const controladorPrevia = useRef<AbortController | null>(null)

  const carregarApoio = useCallback((sinal?: AbortSignal) => {
    setEstadoApoio({ tipo: 'carregando' })
    Promise.all([listarTreinadores(sinal), buscarMapa(sinal), listarItens(sinal)])
      .then(([treinadoresResposta, mapaResposta, itensResposta]) => {
        setEstadoApoio({
          tipo: 'pronto',
          dados: {
            treinadores: treinadoresResposta.items,
            locais: mapaResposta.items,
            itens: itensResposta.items,
          },
        })
      })
      .catch((motivo: unknown) => {
        if (motivo instanceof DOMException && motivo.name === 'AbortError') return
        const mensagem =
          motivo instanceof ApiError
            ? motivo.message
            : 'Nao foi possivel carregar treinadores, mapa e mochila. Verifique a conexao.'
        setEstadoApoio({ tipo: 'erro', mensagem })
      })
  }, [])

  useEffect(() => {
    const controlador = new AbortController()
    carregarApoio(controlador.signal)
    return () => controlador.abort()
  }, [carregarApoio])

  const cargaEntrada = carregaParaEntrada(carga)
  const cargaAssinatura = JSON.stringify(cargaEntrada)

  // Previa ao vivo: uma chamada por mudanca de treinador, destino ou carga,
  // com a anterior sempre cancelada.
  useEffect(() => {
    if (!treinadorId || !localId) {
      controladorPrevia.current?.abort()
      setEstadoPrevia({ tipo: 'incompleto' })
      return
    }

    controladorPrevia.current?.abort()
    const controlador = new AbortController()
    controladorPrevia.current = controlador

    setEstadoPrevia({ tipo: 'carregando' })
    previsualizarExpedicao(
      { treinador_id: treinadorId, local_id: localId, carga: cargaEntrada },
      controlador.signal,
    )
      .then((previa) => {
        if (controlador.signal.aborted) return
        setEstadoPrevia({ tipo: 'pronto', previa })
      })
      .catch((motivo: unknown) => {
        if (controlador.signal.aborted) return
        if (motivo instanceof DOMException && motivo.name === 'AbortError') return
        const mensagem =
          motivo instanceof ApiError
            ? motivo.message
            : 'Nao foi possivel calcular a previa. Verifique a conexao.'
        setEstadoPrevia({ tipo: 'erro', mensagem })
      })

    return () => controlador.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [treinadorId, localId, cargaAssinatura])

  function mudarQuantidade(itemId: string, quantidade: number, estoque: number) {
    const segura = Math.max(0, Math.min(quantidade, estoque))
    setCarga((atual) => ({ ...atual, [itemId]: segura }))
  }

  async function despachar() {
    setErroDespacho(null)
    setDespachando(true)
    try {
      const expedicao = await despacharExpedicao({
        treinador_id: treinadorId,
        local_id: localId,
        carga: cargaEntrada,
      })
      onDespachado(expedicao)
      setTreinadorId('')
      setLocalId('')
      setCarga({})
      carregarApoio()
    } catch (motivo) {
      setErroDespacho(
        motivo instanceof ApiError ? motivo.message : 'Nao foi possivel despachar a expedicao.',
      )
    } finally {
      setDespachando(false)
    }
  }

  if (estadoApoio.tipo === 'carregando') {
    return (
      <section className="despacho-expedicao" aria-label="Despachar expedicao">
        <p>Carregando treinadores, mapa e mochila...</p>
      </section>
    )
  }

  if (estadoApoio.tipo === 'erro') {
    return (
      <section className="despacho-expedicao" aria-label="Despachar expedicao">
        <p role="alert" className="mensagem-erro">
          {estadoApoio.mensagem}
        </p>
        <button type="button" onClick={() => carregarApoio()}>
          Tentar novamente
        </button>
      </section>
    )
  }

  const { treinadores, locais, itens } = estadoApoio.dados

  if (treinadores.length === 0) {
    return (
      <section className="despacho-expedicao" aria-label="Despachar expedicao">
        <p className="aviso-vazio">
          Nenhum treinador no laboratorio. Recrute um para comecar a despachar expedicoes.
        </p>
      </section>
    )
  }

  const destinosDisponiveis = locais.filter((local) => local.estado !== 'FORA_DE_ALCANCE')
  const podeDespachar =
    treinadorId !== '' &&
    localId !== '' &&
    !despachando &&
    estadoPrevia.tipo === 'pronto' &&
    estadoPrevia.previa.valido

  return (
    <section className="despacho-expedicao" aria-label="Despachar expedicao">
      <h2>Nova expedicao</h2>

      <fieldset className="despacho-opcoes">
        <legend>Treinador</legend>
        <ul className="despacho-lista-opcoes" aria-label="Escolher treinador">
          {treinadores.map((treinador) => {
            const semTime = treinador.time.length === 0
            const indisponivel = treinador.ocupado || semTime
            return (
              <li key={treinador.id}>
                <button
                  type="button"
                  aria-pressed={treinador.id === treinadorId}
                  disabled={indisponivel}
                  onClick={() => setTreinadorId(treinador.id)}
                >
                  {treinador.nome} (Nv. {treinador.nivel})
                </button>
                {indisponivel && (
                  <p className="despacho-indisponivel">
                    <span className="rotulo rotulo-indisponivel">Indisponivel</span>{' '}
                    {treinador.ocupado
                      ? `${rotuloStatus(treinador.status)}: nao pode partir em outra expedicao.`
                      : 'Sem Pokemon no time.'}
                    {semTime && !treinador.ocupado && (
                      <>
                        {' '}
                        <Link to="/treinadores">Montar o time</Link>
                      </>
                    )}
                  </p>
                )}
              </li>
            )
          })}
        </ul>
      </fieldset>

      <fieldset className="despacho-opcoes">
        <legend>Destino</legend>
        {destinosDisponiveis.length === 0 && locais.length > 0 && (
          <p className="aviso-vazio">
            Nenhum destino alcancavel ainda. Visite o mapa para ver o que falta desbloquear.
          </p>
        )}
        <ul className="despacho-lista-opcoes" aria-label="Escolher destino">
          {locais.map((local) => {
            const indisponivel = local.estado === 'FORA_DE_ALCANCE'
            return (
              <li key={local.id}>
                <button
                  type="button"
                  aria-pressed={local.id === localId}
                  disabled={indisponivel}
                  onClick={() => setLocalId(local.id)}
                >
                  {local.nome}
                </button>
                {indisponivel && (
                  <p className="despacho-indisponivel">
                    <span className="rotulo rotulo-indisponivel">Indisponivel</span>{' '}
                    {rotuloEstadoLocal(local.estado)}: {local.proximo_passo_nome
                      ? `visite ${local.proximo_passo_nome} antes.`
                      : 'ainda nao ha caminho conhecido ate aqui.'}{' '}
                    <Link to="/mapa">Ver mapa</Link>
                  </p>
                )}
              </li>
            )
          })}
        </ul>
      </fieldset>

      <fieldset className="despacho-opcoes">
        <legend>Carga</legend>
        {itens.length === 0 ? (
          <p className="aviso-vazio">
            A mochila esta vazia. A expedicao pode partir sem itens.
          </p>
        ) : (
          <ul className="despacho-carga">
            {itens.map((item) => (
              <li key={item.item_id} className="despacho-carga-item">
                <label htmlFor={`carga-${item.item_id}`}>
                  {item.nome} (estoque: {item.quantidade})
                </label>
                <input
                  id={`carga-${item.item_id}`}
                  type="number"
                  min={0}
                  max={item.quantidade}
                  value={carga[item.item_id] ?? 0}
                  onChange={(evento) =>
                    mudarQuantidade(item.item_id, Number(evento.target.value), item.quantidade)
                  }
                />
              </li>
            ))}
          </ul>
        )}
      </fieldset>

      {estadoPrevia.tipo === 'incompleto' && (
        <p className="aviso-vazio">Escolha um treinador e um destino para ver a previa.</p>
      )}

      {estadoPrevia.tipo === 'carregando' && <p>Calculando previa...</p>}

      {estadoPrevia.tipo === 'erro' && (
        <p role="alert" className="mensagem-erro">
          {estadoPrevia.mensagem}
        </p>
      )}

      {/*
        Os numeros so aparecem quando a composicao e valida: quando nao e, o
        servidor manda todos nulos, e a tela desenhava "Chance estimada: 0%"
        logo ao lado do motivo da recusa — um numero inventado onde nao existe
        estimativa nenhuma. O motivo, esse, aparece sempre que houver.
      */}
      {estadoPrevia.tipo === 'pronto' && estadoPrevia.previa.valido && (
        <dl className="previa-expedicao" aria-label="Previa da expedicao">
          <div>
            <dt>Duracao</dt>
            <dd>{estadoPrevia.previa.duracao_minutos} min</dd>
          </div>
          <div>
            <dt>Dificuldade</dt>
            <dd>{estadoPrevia.previa.dificuldade}</dd>
          </div>
          <div>
            <dt>Chance estimada</dt>
            <dd>{formatarPercentual(estadoPrevia.previa.chance_estimada ?? 0)}</dd>
          </div>
          <div>
            <dt>Capacidade de bagagem</dt>
            <dd>{estadoPrevia.previa.capacidade_bagagem}</dd>
          </div>
        </dl>
      )}

      {estadoPrevia.tipo === 'pronto' && !estadoPrevia.previa.valido && (
        <p role="alert" className="mensagem-erro">
          {estadoPrevia.previa.motivo}
        </p>
      )}

      {erroDespacho && (
        <p role="alert" className="mensagem-erro">
          {erroDespacho}
        </p>
      )}

      <div className="despacho-acoes">
        <button
          type="button"
          className="botao-primario"
          disabled={!podeDespachar}
          onClick={despachar}
        >
          {despachando ? 'Despachando...' : 'Despachar'}
        </button>
      </div>
    </section>
  )
}
