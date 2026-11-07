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
import { AvatarTreinador } from '@/components/AvatarTreinador'
import { MapaKanto } from '@/components/MapaKanto'
import { SpritePokemon } from '@/components/SpritePokemon'
import { formatarPercentual } from '@/lib/expedicoes'
import { descricaoCategoriaItem } from '@/lib/itens'
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

/** O rotulo acessivel do botao de treinador.
 *
 * E exatamente o texto VISIVEL, e so ele. O WCAG 2.5.3 (Label in Name) exige
 * que o nome acessivel contenha o que esta escrito na tela — quem controla o
 * navegador por voz fala o que le, e "clicar em Ash Nv 2" precisa casar com o
 * nome computado.
 *
 * O time NAO entra aqui de proposito: ele ja e uma `<ul>` IRMA do botao, com
 * papel de lista e um item por Pokemon, navegavel de verdade. Repetir os nomes
 * dentro do rotulo daria a mesma informacao duas vezes e transformaria o nome
 * do botao numa frase longa — que foi justamente o defeito que a revisao pegou.
 */
function rotuloDoTreinador(treinador: TreinadorResumo): string {
  return `${treinador.nome} (Nv. ${treinador.nivel})`
}

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
            : 'Nao foi possivel carregar treinadores, mapa e estoque. Verifique a conexao.'
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
        <p>Carregando treinadores, mapa e estoque...</p>
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
  const localEscolhido = locais.find((local) => local.id === localId) ?? null
  const podeDespachar =
    treinadorId !== '' &&
    localId !== '' &&
    !despachando &&
    estadoPrevia.tipo === 'pronto' &&
    estadoPrevia.previa.valido

  return (
    <section className="despacho-expedicao" aria-label="Despachar expedicao">
      <h2>Nova expedicao</h2>

      {/*
        Duas colunas em tela larga: as escolhas de um lado, a previa do outro,
        FIXA. Antes tudo empilhava, e como a previa reage a cada mudanca o
        professor escolhia no topo, rolava para ver o efeito, e voltava para
        mudar. Com a previa acompanhando a rolagem, a consequencia da escolha
        fica sempre a vista.

        Em tela estreita volta a uma coluna so e a previa desce para o fim —
        nao ha largura para duas, e previa antes das opcoes mostraria o efeito
        de uma escolha que ainda nao existe.
      */}
      <div className="despacho-layout">
        <div className="despacho-etapas">
      <fieldset className="despacho-etapa">
        <legend>1. Treinador</legend>
        <ul className="despacho-lista-opcoes" aria-label="Escolher treinador">
          {treinadores.map((treinador) => {
            const semTime = treinador.time.length === 0
            const indisponivel = treinador.ocupado || semTime
            return (
              <li key={treinador.id}>
                {/*
                  O time ja morou dentro deste botao, como <ul>/<li>. Dois
                  problemas se somavam: <button> so aceita phrasing content
                  (uma <ul> nao e), e todo descendente de role=button e
                  apresentacional pela regra ARIA "Children Presentational:
                  True" — o papel de lista e das imagens do time sumia, e o
                  nome acessivel do botao virava a concatenacao de tudo que
                  sobrava ("Retrato de Ash Ash (Nv. 2) Bulbasaur Nv. 5..."),
                  em vez de "Ash, nivel 2".

                  A correcao: o time sai do botao e vira uma lista de verdade,
                  irma dele dentro do mesmo cartao — continua navegavel por
                  leitor de tela com cada Pokemon no seu proprio item, o que
                  preserva mais informacao do que so citar os nomes dentro de
                  um aria-label. O que sobra dentro do botao (retrato e nome
                  visivel) fica marcado decorativo, e o botao ganha nome
                  acessivel proprio — nome e nivel do treinador, que e o que
                  o professor usa para decidir — independente do que esta
                  desenhado dentro dele.
                */}
                <button
                  type="button"
                  className="despacho-treinador-botao"
                  aria-pressed={treinador.id === treinadorId}
                  /*
                    O rotulo acessivel COMECA pelo texto visivel ("Ash (Nv. 2)")
                    porque o WCAG 2.5.3 exige que o nome contenha o que esta
                    escrito na tela: quem controla o navegador por voz diz o que
                    le, e "clicar em Ash Nv 2" precisa casar. O time vem depois,
                    que e a informacao que falta a quem nao enxerga os sprites.
                  */
                  aria-label={rotuloDoTreinador(treinador)}
                  disabled={indisponivel}
                  onClick={() => setTreinadorId(treinador.id)}
                >
                  <span aria-hidden="true" className="despacho-treinador-decorativo">
                    <AvatarTreinador avatar={treinador.avatar} nome={treinador.nome} />
                    <span className="despacho-treinador-nome">
                      {treinador.nome} (Nv. {treinador.nivel})
                    </span>
                  </span>
                </button>
                {treinador.time.length > 0 && (
                  <ul
                    className="despacho-treinador-time"
                    aria-label={`Time de ${treinador.nome}`}
                  >
                    {treinador.time.map((pokemon) => (
                      <li key={pokemon.id} className="despacho-treinador-time-item">
                        <SpritePokemon caminho={pokemon.sprite} nome={pokemon.nome} />
                        <span className="despacho-treinador-time-nivel">
                          Nv. {pokemon.nivel}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
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

      <fieldset className="despacho-etapa">
        <legend>2. Destino</legend>
        {destinosDisponiveis.length === 0 && locais.length > 0 && (
          <p className="aviso-vazio">
            Nenhum destino alcancavel ainda. Visite o mapa para ver o que falta desbloquear.
          </p>
        )}
        <MapaKanto
          locais={locais}
          modo="selecao"
          selecionadoId={localId || null}
          onSelecionarLocal={setLocalId}
        />
        {/* Alternativa em texto ao mapa: quem navega por teclado ou leitor de
            tela tem aqui um alvo facil, e o destino escolhido fica sempre
            visivel em texto, nao so marcado no desenho. */}
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
        <p className="despacho-destino-escolhido" aria-live="polite">
          {localEscolhido ? (
            <>
              Destino escolhido: <strong>{localEscolhido.nome}</strong>
            </>
          ) : (
            'Nenhum destino escolhido ainda.'
          )}
        </p>
      </fieldset>

      <fieldset className="despacho-etapa">
        <legend>3. Mochila</legend>
        {itens.length === 0 ? (
          <p className="aviso-vazio">
            O estoque esta vazio. A expedicao pode partir sem itens.
          </p>
        ) : (
          <ul className="despacho-carga">
            {itens.map((item) => (
              <li key={item.item_id} className="despacho-carga-item">
                <div className="despacho-carga-item-texto">
                  <label htmlFor={`carga-${item.item_id}`}>
                    {item.nome} (estoque: {item.quantidade})
                  </label>
                  <p className="despacho-carga-item-descricao">
                    {descricaoCategoriaItem(item.categoria)}
                  </p>
                </div>
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
        </div>

        <aside className="despacho-painel" aria-label="Previa e envio">
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
        </aside>
      </div>
    </section>
  )
}
