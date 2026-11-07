/**
 * Montagem de time (spec 004): selecao em lista, sem drag-and-drop. Clicar
 * num Pokemon livre adiciona; clicar num do time remove. Poder e capacidade
 * de bagagem vem sempre da previa do servidor (Artigo II) — o componente
 * nunca calcula o que a composicao vale.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '@/api/client'
import { listarPokemon } from '@/api/pokemon'
import { buscarTreinador, pretenderTime, salvarTime } from '@/api/trainers'
import type { PokemonResumo, PreviaTime, TreinadorDetalhe } from '@/api/tipos'
import { soltarPokemon } from '@/api/viveiro'
import { CartaoPokemon } from '@/components/CartaoPokemon'
import { SpritePokemon } from '@/components/SpritePokemon'
import { rotuloStatus } from '@/lib/treinadores'

export interface MontarTimeProps {
  treinadorId: string
  /** Chamado apos salvar com sucesso, com o treinador ja atualizado. */
  onSalvo?: (treinador: TreinadorDetalhe) => void
  /** Fechar o painel. Com alteracoes pendentes, quem avisa e este componente. */
  onFechar?: () => void
  /**
   * Avisa o pai quando ha alteracoes nao salvas.
   *
   * Necessario porque o painel e remontado por `key` a cada troca de
   * treinador: o aviso interno do botao Fechar nunca chega a rodar nesse
   * caminho, e a composicao pendente evaporava em silencio. Quem controla a
   * selecao precisa saber que ha algo a perder antes de trocar.
   */
  onPendenciasMudaram?: (pendente: boolean) => void
}

type EstadoDetalhe =
  | { tipo: 'carregando' }
  | { tipo: 'erro'; mensagem: string }
  | { tipo: 'pronto'; treinador: TreinadorDetalhe }

type EstadoLivres =
  | { tipo: 'carregando' }
  | { tipo: 'erro'; mensagem: string }
  | { tipo: 'pronto'; itens: PokemonResumo[] }

type EstadoPrevia =
  | { tipo: 'carregando' }
  | { tipo: 'erro'; mensagem: string }
  | { tipo: 'pronto'; previa: PreviaTime }

function idsIguais(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false
  const ordenadoA = [...a].sort()
  const ordenadoB = [...b].sort()
  return ordenadoA.every((id, indice) => id === ordenadoB[indice])
}

const MENSAGEM_ALTERACOES_PENDENTES =
  'O time tem alteracoes que ainda nao foram salvas. Sair mesmo assim?'

export function MontarTime({
  treinadorId,
  onSalvo,
  onFechar,
  onPendenciasMudaram,
}: MontarTimeProps) {
  const [estadoDetalhe, setEstadoDetalhe] = useState<EstadoDetalhe>({ tipo: 'carregando' })
  const [estadoLivres, setEstadoLivres] = useState<EstadoLivres>({ tipo: 'carregando' })
  const [composicao, setComposicao] = useState<string[]>([])
  const [composicaoSalva, setComposicaoSalva] = useState<string[]>([])
  const [estadoPrevia, setEstadoPrevia] = useState<EstadoPrevia | null>(null)
  const [salvando, setSalvando] = useState(false)
  const [erroSalvar, setErroSalvar] = useState<string | null>(null)
  const [soltandoId, setSoltandoId] = useState<string | null>(null)
  const [erroSoltar, setErroSoltar] = useState<string | null>(null)
  const controladorPrevia = useRef<AbortController | null>(null)

  const carregarDetalhe = useCallback(
    (sinal?: AbortSignal) => {
      setEstadoDetalhe({ tipo: 'carregando' })
      buscarTreinador(treinadorId, sinal)
        .then((treinador) => {
          const idsAtuais = treinador.time.map((pokemon) => pokemon.id)
          setEstadoDetalhe({ tipo: 'pronto', treinador })
          setComposicao(idsAtuais)
          setComposicaoSalva(idsAtuais)
        })
        .catch((motivo: unknown) => {
          if (motivo instanceof DOMException && motivo.name === 'AbortError') return
          const mensagem =
            motivo instanceof ApiError
              ? motivo.message
              : 'Nao foi possivel carregar o treinador. Verifique a conexao.'
          setEstadoDetalhe({ tipo: 'erro', mensagem })
        })
    },
    [treinadorId],
  )

  useEffect(() => {
    const controlador = new AbortController()
    carregarDetalhe(controlador.signal)
    return () => controlador.abort()
  }, [carregarDetalhe])

  const carregarLivres = useCallback((sinal?: AbortSignal) => {
    setEstadoLivres({ tipo: 'carregando' })
    listarPokemon({ livre: true, pageSize: 100 }, sinal)
      .then((resposta) => setEstadoLivres({ tipo: 'pronto', itens: resposta.items }))
      .catch((motivo: unknown) => {
        if (motivo instanceof DOMException && motivo.name === 'AbortError') return
        const mensagem =
          motivo instanceof ApiError
            ? motivo.message
            : 'Nao foi possivel carregar os Pokemon livres. Verifique a conexao.'
        setEstadoLivres({ tipo: 'erro', mensagem })
      })
  }, [])

  useEffect(() => {
    const controlador = new AbortController()
    carregarLivres(controlador.signal)
    return () => controlador.abort()
  }, [carregarLivres])

  const treinadorCarregado = estadoDetalhe.tipo === 'pronto' ? estadoDetalhe.treinador : null
  const ocupado = treinadorCarregado?.ocupado === true

  // Previa ao vivo (plan.md): uma chamada por mudanca de composicao, com a
  // anterior sempre cancelada — o professor clica rapido, e uma resposta
  // antiga chegando depois da nova mostraria o poder de outra composicao.
  useEffect(() => {
    if (!treinadorCarregado || ocupado) return

    controladorPrevia.current?.abort()
    const controlador = new AbortController()
    controladorPrevia.current = controlador

    setEstadoPrevia({ tipo: 'carregando' })
    pretenderTime(treinadorId, composicao, controlador.signal)
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
  }, [composicao, treinadorId, ocupado, treinadorCarregado])

  function alternarSelecao(id: string) {
    setComposicao((atual) =>
      atual.includes(id) ? atual.filter((item) => item !== id) : [...atual, id],
    )
  }

  function fechar() {
    if (!idsIguais(composicao, composicaoSalva)) {
      if (!window.confirm(MENSAGEM_ALTERACOES_PENDENTES)) return
    }
    onFechar?.()
  }

  async function salvar() {
    setErroSalvar(null)
    setSalvando(true)
    try {
      const atualizado = await salvarTime(treinadorId, composicao)
      const idsAtuais = atualizado.time.map((pokemon) => pokemon.id)
      setEstadoDetalhe({ tipo: 'pronto', treinador: atualizado })
      setComposicao(idsAtuais)
      setComposicaoSalva(idsAtuais)
      carregarLivres()
      onSalvo?.(atualizado)
    } catch (motivo) {
      setErroSalvar(
        motivo instanceof ApiError ? motivo.message : 'Nao foi possivel salvar o time.',
      )
    } finally {
      setSalvando(false)
    }
  }

  /**
   * Solta um Pokemon do time deste treinador (spec 008, criterio 8): o
   * unico lugar da interface, alem do viveiro, onde `DELETE /pokemon/{id}`
   * e chamado — aqui o Pokemon esta visivel porque tem treinador, nao
   * porque esta livre. Mesma confirmacao nomeada e irreversivel do viveiro
   * (`pages/Viveiro.tsx`). So aparece quando o treinador esta disponivel: a
   * secao de "ocupado", acima, retorna antes de chegar aqui.
   */
  async function soltar(pokemon: PokemonResumo) {
    const confirmado = window.confirm(
      `Soltar ${pokemon.nome} (Nv. ${pokemon.nivel})? Ele volta a natureza, nao rende nada, e esta acao nao pode ser desfeita.`,
    )
    if (!confirmado) return

    setErroSoltar(null)
    setSoltandoId(pokemon.id)
    try {
      await soltarPokemon(pokemon.id)
      const atualizado = await buscarTreinador(treinadorId)
      const idsAtuais = atualizado.time.map((p) => p.id)
      setEstadoDetalhe({ tipo: 'pronto', treinador: atualizado })
      setComposicao(idsAtuais)
      setComposicaoSalva(idsAtuais)
      carregarLivres()
      onSalvo?.(atualizado)
    } catch (motivo) {
      setErroSoltar(
        motivo instanceof ApiError ? motivo.message : 'Nao foi possivel soltar este Pokemon.',
      )
    } finally {
      setSoltandoId(null)
    }
  }

  const temAlteracoesPendentes = !idsIguais(composicao, composicaoSalva)

  // Notifica o pai, que e quem controla a selecao e precisa avisar antes de
  // trocar de treinador. A limpeza no desmonte evita deixar o pai achando que
  // ainda ha pendencias de um painel que nem existe mais.
  useEffect(() => {
    onPendenciasMudaram?.(temAlteracoesPendentes)
    return () => onPendenciasMudaram?.(false)
  }, [temAlteracoesPendentes, onPendenciasMudaram])

  if (estadoDetalhe.tipo === 'carregando') {
    return (
      <section className="montar-time" aria-label="Montar time">
        <p>Carregando treinador...</p>
      </section>
    )
  }

  if (estadoDetalhe.tipo === 'erro') {
    return (
      <section className="montar-time" aria-label="Montar time">
        <p role="alert" className="mensagem-erro">
          {estadoDetalhe.mensagem}
        </p>
        <button type="button" onClick={() => carregarDetalhe()}>
          Tentar novamente
        </button>
      </section>
    )
  }

  // Reatribuido a partir de `estadoDetalhe` ja estreitado para 'pronto' pelos
  // dois retornos acima: o `treinador` do topo da funcao segue `| null` para
  // os hooks, que rodam antes de qualquer retorno condicional existir.
  const { treinador } = estadoDetalhe

  // Mapa de todo Pokemon que a tela conhece, para resolver os ids da
  // composicao tanto aos ja atribuidos a este treinador quanto aos livres.
  const mapaPokemon = new Map<string, PokemonResumo>()
  treinador.time.forEach((pokemon) => mapaPokemon.set(pokemon.id, pokemon))
  if (estadoLivres.tipo === 'pronto') {
    estadoLivres.itens.forEach((pokemon) => mapaPokemon.set(pokemon.id, pokemon))
  }

  const pokemonDoTime = composicao
    .map((id) => mapaPokemon.get(id))
    .filter((pokemon): pokemon is PokemonResumo => pokemon !== undefined)

  if (ocupado) {
    return (
      <section className="montar-time" aria-label={`Time de ${treinador.nome}`}>
        <h2>{treinador.nome}</h2>
        <p role="alert" className="mensagem-erro">
          Treinador {rotuloStatus(treinador.status).toLowerCase()}: nao e possivel alterar o
          time agora.
        </p>

        <dl className="previa-time" aria-label="Situacao atual do time">
          <div>
            <dt>Poder do time</dt>
            <dd>{treinador.poder}</dd>
          </div>
          <div>
            <dt>Capacidade de bagagem</dt>
            <dd>{treinador.capacidade_bagagem}</dd>
          </div>
        </dl>

        {treinador.time.length === 0 ? (
          <p className="aviso-vazio">Este treinador partiu sem Pokemon no time.</p>
        ) : (
          <ul className="montar-time-lista-somente-leitura" aria-label={`Time atual de ${treinador.nome}`}>
            {treinador.time.map((pokemon) => (
              <li key={pokemon.id}>
                <SpritePokemon caminho={pokemon.sprite} nome={pokemon.nome} />
                <span>
                  {pokemon.nome} (Nv. {pokemon.nivel})
                </span>
              </li>
            ))}
          </ul>
        )}

        {onFechar && (
          <button type="button" onClick={onFechar}>
            Fechar
          </button>
        )}
      </section>
    )
  }

  // Disponiveis = livres no laboratorio MAIS os que ja estao no time deste
  // treinador, menos o que esta na composicao atual.
  //
  // Sem a segunda parcela, retirar um Pokemon do time o fazia desaparecer das
  // duas colunas: ele sai de `composicao`, e nunca esteve em `estadoLivres`
  // porque o servidor so considera livre quem tem treinador_id nulo. Nao havia
  // como devolve-lo sem fechar e reabrir o painel.
  const candidatos = new Map<string, PokemonResumo>()
  treinador.time.forEach((pokemon) => candidatos.set(pokemon.id, pokemon))
  if (estadoLivres.tipo === 'pronto') {
    estadoLivres.itens.forEach((pokemon) => candidatos.set(pokemon.id, pokemon))
  }

  const livresDisponiveis = [...candidatos.values()]
    .filter((pokemon) => !composicao.includes(pokemon.id))
    .sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'))

  const dirty = temAlteracoesPendentes
  const composicaoInvalida = estadoPrevia?.tipo === 'pronto' && !estadoPrevia.previa.valido

  return (
    <section className="montar-time" aria-label={`Montar time de ${treinador.nome}`}>
      <h2>Time de {treinador.nome}</h2>

      <dl className="previa-time" aria-label="Previa da composicao">
        <div>
          <dt>Poder do time</dt>
          <dd>{estadoPrevia?.tipo === 'pronto' ? estadoPrevia.previa.poder : 'Calculando...'}</dd>
        </div>
        <div>
          <dt>Capacidade de bagagem</dt>
          <dd>
            {estadoPrevia?.tipo === 'pronto' ? estadoPrevia.previa.capacidade_bagagem : '--'}
            <span className="dica-campo">
              {' '}
              capturas que cabem nesta expedicao; cresce quando o time encolhe
            </span>
          </dd>
        </div>
      </dl>

      {estadoPrevia?.tipo === 'pronto' && !estadoPrevia.previa.valido && (
        <p role="alert" className="mensagem-erro">
          {estadoPrevia.previa.motivo}
        </p>
      )}

      {estadoPrevia?.tipo === 'erro' && (
        <p role="alert" className="mensagem-erro">
          {estadoPrevia.mensagem}
        </p>
      )}

      {erroSoltar && (
        <p role="alert" className="mensagem-erro">
          {erroSoltar}
        </p>
      )}

      <div className="montar-time-colunas">
        <div>
          <h3>{`Time atual (${pokemonDoTime.length} / ${treinador.tamanho_maximo_time})`}</h3>
          {pokemonDoTime.length === 0 ? (
            <p className="aviso-vazio">
              Nenhum Pokemon no time. Escolha entre os livres para montar.
            </p>
          ) : (
            <ul className="montar-time-lista" aria-label="Pokemon no time">
              {pokemonDoTime.map((pokemon) => (
                <li key={pokemon.id}>
                  <CartaoPokemon pokemon={pokemon} selecionado onSelecionar={alternarSelecao} />
                  <button
                    type="button"
                    className="botao-perigo"
                    disabled={soltandoId === pokemon.id}
                    onClick={() => soltar(pokemon)}
                  >
                    {soltandoId === pokemon.id ? 'Soltando...' : 'Soltar'}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div>
          <h3>Pokemon livres</h3>
          {estadoLivres.tipo === 'carregando' && <p>Carregando Pokemon livres...</p>}

          {estadoLivres.tipo === 'erro' && (
            <div>
              <p role="alert" className="mensagem-erro">
                {estadoLivres.mensagem}
              </p>
              <button type="button" onClick={() => carregarLivres()}>
                Tentar novamente
              </button>
            </div>
          )}

          {estadoLivres.tipo === 'pronto' &&
            (livresDisponiveis.length === 0 ? (
              <p className="aviso-vazio">
                Nenhum Pokemon livre no laboratorio. Volte apos uma expedicao trazer capturas.
              </p>
            ) : (
              <ul className="montar-time-lista" aria-label="Pokemon livres">
                {livresDisponiveis.map((pokemon) => (
                  <li key={pokemon.id}>
                    <CartaoPokemon pokemon={pokemon} onSelecionar={alternarSelecao} />
                  </li>
                ))}
              </ul>
            ))}
        </div>
      </div>

      {erroSalvar && (
        <p role="alert" className="mensagem-erro">
          {erroSalvar}
        </p>
      )}

      <div className="montar-time-acoes">
        {onFechar && (
          <button type="button" onClick={fechar}>
            Fechar
          </button>
        )}
        <button
          type="button"
          className="botao-primario"
          disabled={salvando || !dirty || composicaoInvalida}
          onClick={salvar}
        >
          {salvando ? 'Salvando...' : 'Salvar time'}
        </button>
      </div>
    </section>
  )
}
