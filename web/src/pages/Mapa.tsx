import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { buscarLocal, buscarMapa } from '@/api/mapa'
import { listarTreinadores } from '@/api/trainers'
import type { LocalDetalhado, RespostaMapa, TreinadorResumo } from '@/api/tipos'
import { CartaoLocal } from '@/components/CartaoLocal'
import { EspeciesAvistadas } from '@/components/EspeciesAvistadas'
import { rotuloEstadoLocal, rotuloTipoLocal } from '@/lib/mapa'

type EstadoLista =
  | { tipo: 'carregando' }
  | { tipo: 'erro'; mensagem: string }
  | { tipo: 'pronto'; resposta: RespostaMapa }

type EstadoDetalhe =
  | { tipo: 'vazio' }
  | { tipo: 'carregando' }
  | { tipo: 'erro'; mensagem: string }
  | { tipo: 'pronto'; detalhe: LocalDetalhado }

export function Mapa() {
  const [estadoLista, setEstadoLista] = useState<EstadoLista>({ tipo: 'carregando' })
  const [selecionadoId, setSelecionadoId] = useState<string | null>(null)
  const [estadoDetalhe, setEstadoDetalhe] = useState<EstadoDetalhe>({ tipo: 'vazio' })
  const [treinadores, setTreinadores] = useState<TreinadorResumo[]>([])
  const [treinadorId, setTreinadorId] = useState('')

  const carregarLista = useCallback(() => {
    setEstadoLista({ tipo: 'carregando' })
    buscarMapa()
      .then((resposta) => setEstadoLista({ tipo: 'pronto', resposta }))
      .catch((motivo: unknown) => {
        const mensagem =
          motivo instanceof ApiError
            ? motivo.message
            : 'Nao foi possivel carregar o mapa. Verifique a conexao.'
        setEstadoLista({ tipo: 'erro', mensagem })
      })
  }, [])

  useEffect(() => {
    carregarLista()
  }, [carregarLista])

  // A lista de treinadores so alimenta o seletor opcional da estimativa de
  // duracao (plan.md): se essa chamada falhar, o mapa continua inteiramente
  // util com a duracao base, entao a falha aqui nao vira um estado de erro de
  // tela inteira — so o seletor nao aparece.
  useEffect(() => {
    listarTreinadores()
      .then((resposta) => setTreinadores(resposta.items))
      .catch(() => setTreinadores([]))
  }, [])

  const carregarDetalhe = useCallback(
    (id: string, treinador: string, sinal?: AbortSignal) => {
      setEstadoDetalhe({ tipo: 'carregando' })
      buscarLocal(id, treinador || undefined, sinal)
        .then((detalhe) => setEstadoDetalhe({ tipo: 'pronto', detalhe }))
        .catch((motivo: unknown) => {
          if (motivo instanceof DOMException && motivo.name === 'AbortError') return
          const mensagem =
            motivo instanceof ApiError
              ? motivo.message
              : 'Nao foi possivel carregar o local. Verifique a conexao.'
          setEstadoDetalhe({ tipo: 'erro', mensagem })
        })
    },
    [],
  )

  useEffect(() => {
    if (!selecionadoId) {
      setEstadoDetalhe({ tipo: 'vazio' })
      return
    }
    const controlador = new AbortController()
    carregarDetalhe(selecionadoId, treinadorId, controlador.signal)
    return () => controlador.abort()
  }, [selecionadoId, treinadorId, carregarDetalhe])

  function selecionar(id: string) {
    setSelecionadoId((atual) => (atual === id ? null : id))
  }

  if (estadoLista.tipo === 'carregando') {
    return (
      <main className="tela-mapa">
        <p>Carregando mapa...</p>
      </main>
    )
  }

  if (estadoLista.tipo === 'erro') {
    return (
      <main className="tela-mapa">
        <p role="alert" className="mensagem-erro">
          {estadoLista.mensagem}
        </p>
        <button type="button" onClick={carregarLista}>
          Tentar novamente
        </button>
      </main>
    )
  }

  const { resposta } = estadoLista

  if (resposta.items.length === 0) {
    return (
      <main className="tela-mapa">
        <p className="aviso-vazio">
          O mapa de Kanto ainda nao tem locais cadastrados. Confira o seed do laboratorio.
        </p>
      </main>
    )
  }

  // A ordem vem do servidor, por custo de viagem (ver lib/mapa.ts).
  const locaisOrdenados = resposta.items

  return (
    <main className="tela-mapa">
      <header>
        <h1>Mapa de Kanto</h1>
        <Link to="/laboratorio">Voltar ao laboratorio</Link>
      </header>

      <p className="mapa-resumo">
        {resposta.visitados} de {resposta.total} locais visitados
      </p>

      <div className="mapa-layout">
        <ul className="lista-locais-grade">
          {locaisOrdenados.map((local) => (
            <li key={local.id}>
              <CartaoLocal
                local={local}
                selecionado={local.id === selecionadoId}
                onSelecionar={selecionar}
              />
            </li>
          ))}
        </ul>

        {selecionadoId && (
          <section className="detalhe-local" aria-label="Detalhe do local">
            {treinadores.length > 0 && (
              <div className="detalhe-local-seletor">
                <label htmlFor="mapa-seletor-treinador">Estimar com o treinador</label>
                <select
                  id="mapa-seletor-treinador"
                  value={treinadorId}
                  onChange={(evento) => setTreinadorId(evento.target.value)}
                >
                  <option value="">Duracao base, sem treinador</option>
                  {treinadores.map((treinador) => (
                    <option key={treinador.id} value={treinador.id}>
                      {treinador.nome} (Nv. {treinador.nivel})
                    </option>
                  ))}
                </select>
              </div>
            )}

            {estadoDetalhe.tipo === 'carregando' && <p>Carregando local...</p>}

            {estadoDetalhe.tipo === 'erro' && (
              <div>
                <p role="alert" className="mensagem-erro">
                  {estadoDetalhe.mensagem}
                </p>
                <button
                  type="button"
                  onClick={() => carregarDetalhe(selecionadoId, treinadorId)}
                >
                  Tentar novamente
                </button>
              </div>
            )}

            {estadoDetalhe.tipo === 'pronto' && <DetalheLocal detalhe={estadoDetalhe.detalhe} />}
          </section>
        )}
      </div>
    </main>
  )
}

/** Conteudo do painel de detalhe: dados do local, mais as especies avistadas. */
function DetalheLocal({ detalhe }: { detalhe: LocalDetalhado }) {
  return (
    <div aria-label={`Detalhe de ${detalhe.nome}`}>
      <h2>{detalhe.nome}</h2>
      <p className="detalhe-local-tipo">
        {rotuloTipoLocal(detalhe.tipo)} — {rotuloEstadoLocal(detalhe.estado)}
      </p>

      <dl className="detalhe-local-stats" aria-label="Dados do local">
        <div>
          <dt>Dificuldade</dt>
          <dd>{detalhe.nivel_dificuldade}</dd>
        </div>
        <div>
          <dt>Nivel selvagem</dt>
          <dd>
            {detalhe.nivel_selvagem_min} a {detalhe.nivel_selvagem_max}
          </dd>
        </div>
        <div>
          <dt>Encontros por expedicao</dt>
          <dd>{detalhe.encontros_base}</dd>
        </div>
        <div>
          <dt>Duracao estimada</dt>
          <dd>
            {detalhe.duracao_estimada_minutos !== null
              ? `${detalhe.duracao_estimada_minutos} min`
              : 'Nao se aplica: local fora de alcance'}
          </dd>
        </div>
      </dl>

      <h3>Especies avistadas</h3>
      <EspeciesAvistadas especies={detalhe.especies_avistadas} />
    </div>
  )
}
