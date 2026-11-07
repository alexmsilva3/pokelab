/**
 * Selecao dos Pokemon no aceite de uma entrega (spec 008, tarefa 18). O
 * professor escolhe QUAIS Pokemon mandar entre os que atendem ao pedido —
 * com quatro Pidgey e um pedido de dois, qual par sai e decisao dele, porque
 * a recompensa paga por nivel (SDD 4.9). Por isso cada candidato mostra o
 * proprio nivel, nunca so o nome da especie.
 *
 * Esta e a unica operacao do jogo que destroi Pokemon por escolha do
 * professor: a confirmacao NOMEIA quem sai antes de qualquer chamada a API,
 * e o botao de confirmar fica desabilitado enquanto a chamada corre — dois
 * aceites simultaneos sao idempotentes no servidor, mas piscar a interface
 * nao ajuda ninguem a entender o que aconteceu.
 */
import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '@/api/client'
import { aceitarEntrega } from '@/api/deliveries'
import { listarPokemon } from '@/api/pokemon'
import { listarTreinadores } from '@/api/trainers'
import type { EntregaLer, PokemonResumo, TreinadorResumo } from '@/api/tipos'

export interface AceitarEntregaProps {
  entrega: EntregaLer
  /** Chamado apos o aceite ter sucesso, com a entrega ja EM_CURSO. */
  onAceito: (entregaAtualizada: EntregaLer) => void
  onCancelar: () => void
}

type EstadoApoio =
  | { tipo: 'carregando' }
  | { tipo: 'erro'; mensagem: string }
  | { tipo: 'pronto'; pokemonLivres: PokemonResumo[]; treinadoresDisponiveis: TreinadorResumo[] }

export function AceitarEntrega({ entrega, onAceito, onCancelar }: AceitarEntregaProps) {
  const [estadoApoio, setEstadoApoio] = useState<EstadoApoio>({ tipo: 'carregando' })
  const [selecaoPorEspecie, setSelecaoPorEspecie] = useState<Record<number, string[]>>({})
  const [treinadorId, setTreinadorId] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [erroAceite, setErroAceite] = useState<string | null>(null)

  const carregarApoio = useCallback((sinal?: AbortSignal) => {
    setEstadoApoio({ tipo: 'carregando' })
    Promise.all([
      // 100 cobre o viveiro inteiro (CAPACIDADE_VIVEIRO = 50) mesmo
      // transbordado: `livre` ja exclui quem esta em time, em expedicao ou
      // comprometido com outra entrega (spec 004, nota de "vai divergir
      // quando a Fase 8 existir" — que e agora).
      listarPokemon({ livre: true, pageSize: 100 }, sinal),
      listarTreinadores(sinal),
    ])
      .then(([pokemonResposta, treinadoresResposta]) => {
        setEstadoApoio({
          tipo: 'pronto',
          pokemonLivres: pokemonResposta.items,
          treinadoresDisponiveis: treinadoresResposta.items.filter((t) => !t.ocupado),
        })
      })
      .catch((motivo: unknown) => {
        if (motivo instanceof DOMException && motivo.name === 'AbortError') return
        const mensagem =
          motivo instanceof ApiError
            ? motivo.message
            : 'Nao foi possivel carregar os candidatos ao aceite. Verifique a conexao.'
        setEstadoApoio({ tipo: 'erro', mensagem })
      })
  }, [])

  useEffect(() => {
    const controlador = new AbortController()
    carregarApoio(controlador.signal)
    return () => controlador.abort()
  }, [carregarApoio])

  function alternarCandidato(especieId: number, quantidade: number, pokemonId: string) {
    setSelecaoPorEspecie((atual) => {
      const selecionados = atual[especieId] ?? []
      if (selecionados.includes(pokemonId)) {
        return { ...atual, [especieId]: selecionados.filter((id) => id !== pokemonId) }
      }
      if (selecionados.length >= quantidade) return atual
      return { ...atual, [especieId]: [...selecionados, pokemonId] }
    })
  }

  if (estadoApoio.tipo === 'carregando') {
    return (
      <section className="aceitar-entrega" aria-label={`Aceitar pedido: ${entrega.titulo}`}>
        <p>Carregando Pokemon e treinadores disponiveis...</p>
      </section>
    )
  }

  if (estadoApoio.tipo === 'erro') {
    return (
      <section className="aceitar-entrega" aria-label={`Aceitar pedido: ${entrega.titulo}`}>
        <p role="alert" className="mensagem-erro">
          {estadoApoio.mensagem}
        </p>
        <button type="button" onClick={() => carregarApoio()}>
          Tentar novamente
        </button>
      </section>
    )
  }

  const { pokemonLivres, treinadoresDisponiveis } = estadoApoio

  const candidatosPorEspecie = new Map<number, PokemonResumo[]>()
  entrega.requisitos.forEach((requisito) => {
    candidatosPorEspecie.set(
      requisito.especie_id,
      pokemonLivres.filter((pokemon) => pokemon.especie_id === requisito.especie_id),
    )
  })

  const conjuntoCompleto = entrega.requisitos.every(
    (requisito) => (selecaoPorEspecie[requisito.especie_id] ?? []).length === requisito.quantidade,
  )
  const podeConfirmar = conjuntoCompleto && treinadorId !== '' && !enviando

  function pokemonSelecionados(): PokemonResumo[] {
    const ids = Object.values(selecaoPorEspecie).flat()
    return pokemonLivres.filter((pokemon) => ids.includes(pokemon.id))
  }

  async function confirmar() {
    const selecionados = pokemonSelecionados()
    const nomes = selecionados.map((pokemon) => `${pokemon.nome} (Nv. ${pokemon.nivel})`).join(', ')
    const confirmado = window.confirm(
      `Enviar ${nomes} para ${entrega.local_destino_nome}? Eles saem do laboratorio para sempre, em troca de moeda e experiencia.`,
    )
    if (!confirmado) return

    setErroAceite(null)
    setEnviando(true)
    try {
      const entregaAtualizada = await aceitarEntrega(entrega.id, {
        treinador_id: treinadorId,
        pokemon_ids: selecionados.map((pokemon) => pokemon.id),
      })
      onAceito(entregaAtualizada)
    } catch (motivo) {
      setErroAceite(
        motivo instanceof ApiError ? motivo.message : 'Nao foi possivel aceitar esta entrega.',
      )
    } finally {
      setEnviando(false)
    }
  }

  return (
    <section className="aceitar-entrega" aria-label={`Aceitar pedido: ${entrega.titulo}`}>
      {entrega.requisitos.map((requisito) => {
        const candidatos = candidatosPorEspecie.get(requisito.especie_id) ?? []
        const selecionados = selecaoPorEspecie[requisito.especie_id] ?? []
        return (
          <fieldset key={requisito.especie_id} className="aceitar-entrega-requisito">
            <legend>
              {requisito.especie_nome} ({selecionados.length} / {requisito.quantidade})
            </legend>
            {candidatos.length === 0 ? (
              <p className="aviso-vazio">
                Nenhum {requisito.especie_nome} livre no viveiro para escolher.
              </p>
            ) : (
              <ul
                className="aceitar-entrega-candidatos"
                aria-label={`Candidatos de ${requisito.especie_nome}`}
              >
                {candidatos.map((pokemon) => {
                  const selecionado = selecionados.includes(pokemon.id)
                  const noLimite = !selecionado && selecionados.length >= requisito.quantidade
                  return (
                    <li key={pokemon.id}>
                      <button
                        type="button"
                        aria-pressed={selecionado}
                        disabled={noLimite}
                        onClick={() =>
                          alternarCandidato(requisito.especie_id, requisito.quantidade, pokemon.id)
                        }
                      >
                        {pokemon.nome} (Nv. {pokemon.nivel})
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}
          </fieldset>
        )
      })}

      <fieldset className="aceitar-entrega-treinadores">
        <legend>Treinador</legend>
        {treinadoresDisponiveis.length === 0 ? (
          <p className="aviso-vazio">
            Nenhum treinador disponivel. Aguarde um voltar de expedicao ou de outra entrega.
          </p>
        ) : (
          <ul aria-label="Escolher treinador para a entrega">
            {treinadoresDisponiveis.map((treinador) => (
              <li key={treinador.id}>
                <button
                  type="button"
                  aria-pressed={treinador.id === treinadorId}
                  onClick={() => setTreinadorId(treinador.id)}
                >
                  {treinador.nome} (Nv. {treinador.nivel})
                </button>
              </li>
            ))}
          </ul>
        )}
      </fieldset>

      {erroAceite && (
        <p role="alert" className="mensagem-erro">
          {erroAceite}
        </p>
      )}

      <div className="aceitar-entrega-acoes">
        <button type="button" onClick={onCancelar}>
          Cancelar
        </button>
        <button type="button" className="botao-perigo" disabled={!podeConfirmar} onClick={confirmar}>
          {enviando ? 'Enviando...' : 'Confirmar aceite'}
        </button>
      </div>
    </section>
  )
}
