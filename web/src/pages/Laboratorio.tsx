import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { buscarPerfil } from '@/api/auth'
import { ApiError } from '@/api/client'
import { listarItens } from '@/api/itens'
import { listarPokemon } from '@/api/pokemon'
import type {
  ItemEmEstoque,
  PerfilCompleto,
  PokemonDetalhe,
  RespostaListaPokemon,
  TipoPokemon,
} from '@/api/tipos'
import { FichaPokemon } from '@/components/FichaPokemon'
import { FiltrosPokemon, type ValoresFiltroPokemon } from '@/components/FiltrosPokemon'
import { ListaPokemon } from '@/components/ListaPokemon'
import { Mochila } from '@/components/Mochila'
import { limparSessao } from '@/store/auth'

const TAMANHO_PAGINA = 20

type EstadoPerfil =
  | { tipo: 'carregando' }
  | { tipo: 'erro'; mensagem: string }
  | { tipo: 'pronto'; perfil: PerfilCompleto }

type EstadoLista =
  | { tipo: 'carregando' }
  | { tipo: 'erro'; mensagem: string }
  | { tipo: 'pronto'; resposta: RespostaListaPokemon }

type EstadoItens =
  | { tipo: 'carregando' }
  | { tipo: 'erro'; mensagem: string }
  | { tipo: 'pronto'; itens: ItemEmEstoque[] }

const NIVEL_MINIMO = 1
const NIVEL_MAXIMO = 100

/**
 * Le um nivel da URL, descartando o que o servidor recusaria.
 *
 * A URL e editavel por qualquer um. Antes, `Number('abc')` virava NaN, passava
 * pela checagem de `!== undefined` e ia para a query string, e o acervo inteiro
 * sumia atras de um 422 sem o professor entender por que.
 */
function lerNivelDaUrl(bruto: string | null): number | undefined {
  if (bruto === null || bruto.trim() === '') return undefined
  const valor = Number(bruto)
  if (!Number.isInteger(valor)) return undefined
  if (valor < NIVEL_MINIMO || valor > NIVEL_MAXIMO) return undefined
  return valor
}

function lerFiltrosDaUrl(parametros: URLSearchParams): ValoresFiltroPokemon {
  const tipo = parametros.get('tipo')
  const atribuido = parametros.get('atribuido')

  return {
    tipo: tipo ? (tipo as TipoPokemon) : undefined,
    nivelMin: lerNivelDaUrl(parametros.get('nivel_min')),
    nivelMax: lerNivelDaUrl(parametros.get('nivel_max')),
    atribuido: atribuido === null ? undefined : atribuido === 'true',
  }
}

function lerPaginaDaUrl(parametros: URLSearchParams): number {
  const page = Number(parametros.get('page') ?? '1')
  return Number.isFinite(page) && page > 0 ? page : 1
}

export function Laboratorio() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const [estadoPerfil, setEstadoPerfil] = useState<EstadoPerfil>({ tipo: 'carregando' })
  const [estadoLista, setEstadoLista] = useState<EstadoLista>({ tipo: 'carregando' })
  const [estadoItens, setEstadoItens] = useState<EstadoItens>({ tipo: 'carregando' })
  const [selecionadoId, setSelecionadoId] = useState<string | null>(null)
  const [tentativaLista, setTentativaLista] = useState(0)

  const filtros = lerFiltrosDaUrl(searchParams)

  const carregarPerfil = useCallback(() => {
    setEstadoPerfil({ tipo: 'carregando' })
    buscarPerfil()
      .then((perfil) => setEstadoPerfil({ tipo: 'pronto', perfil }))
      .catch((motivo: unknown) => {
        const mensagem =
          motivo instanceof ApiError
            ? motivo.message
            : 'Nao foi possivel carregar o laboratorio. Verifique a conexao.'
        setEstadoPerfil({ tipo: 'erro', mensagem })
      })
  }, [])

  useEffect(() => {
    carregarPerfil()
  }, [carregarPerfil])

  const carregarItens = useCallback(() => {
    setEstadoItens({ tipo: 'carregando' })
    listarItens()
      .then((resposta) => setEstadoItens({ tipo: 'pronto', itens: resposta.items }))
      .catch((motivo: unknown) => {
        const mensagem =
          motivo instanceof ApiError
            ? motivo.message
            : 'Nao foi possivel carregar a mochila. Verifique a conexao.'
        setEstadoItens({ tipo: 'erro', mensagem })
      })
  }, [])

  useEffect(() => {
    carregarItens()
  }, [carregarItens])

  // Condicao de corrida (plan.md): se o professor troca de filtro rapido, a
  // resposta antiga pode chegar depois da nova. Cada efeito cria o proprio
  // controlador e aborta o da rodada anterior; uma resposta cujo sinal ja
  // foi abortado e descartada no catch.
  useEffect(() => {
    const controlador = new AbortController()
    const filtrosAtuais = lerFiltrosDaUrl(searchParams)
    const paginaAtual = lerPaginaDaUrl(searchParams)

    setEstadoLista({ tipo: 'carregando' })
    listarPokemon(
      { ...filtrosAtuais, page: paginaAtual, pageSize: TAMANHO_PAGINA },
      controlador.signal,
    )
      .then((resposta) => {
        // Resposta de um filtro que o professor ja trocou: o controlador foi
        // abortado, mas uma promessa resolvida nao rejeita sozinha so por
        // isso. Descartar aqui e a segunda linha de defesa contra a
        // condicao de corrida, independente do fetch respeitar o abort.
        if (controlador.signal.aborted) return
        setEstadoLista({ tipo: 'pronto', resposta })
      })
      .catch((motivo: unknown) => {
        if (controlador.signal.aborted) return
        if (motivo instanceof DOMException && motivo.name === 'AbortError') return
        const mensagem =
          motivo instanceof ApiError
            ? motivo.message
            : 'Nao foi possivel carregar o acervo. Verifique a conexao.'
        setEstadoLista({ tipo: 'erro', mensagem })
      })

    return () => controlador.abort()
  }, [searchParams, tentativaLista])

  function aplicarFiltros(novosValores: ValoresFiltroPokemon) {
    const proximos = new URLSearchParams()
    if (novosValores.tipo) proximos.set('tipo', novosValores.tipo)
    if (novosValores.nivelMin !== undefined) {
      proximos.set('nivel_min', String(novosValores.nivelMin))
    }
    if (novosValores.nivelMax !== undefined) {
      proximos.set('nivel_max', String(novosValores.nivelMax))
    }
    if (novosValores.atribuido !== undefined) {
      proximos.set('atribuido', String(novosValores.atribuido))
    }
    proximos.set('page', '1')
    // replace: digitar "15" no filtro de nivel dispara dois onChange, e sem
    // isso o botao voltar do navegador percorreria caractere por caractere.
    setSearchParams(proximos, { replace: true })
  }

  function mudarPagina(novaPagina: number) {
    const proximos = new URLSearchParams(searchParams)
    proximos.set('page', String(novaPagina))
    setSearchParams(proximos)
  }

  function aoAtualizarApelido(detalhe: PokemonDetalhe) {
    setEstadoLista((atual) => {
      if (atual.tipo !== 'pronto') return atual
      return {
        tipo: 'pronto',
        resposta: {
          ...atual.resposta,
          items: atual.resposta.items.map((item) =>
            item.id === detalhe.id ? { ...item, nome: detalhe.nome } : item,
          ),
        },
      }
    })
  }

  function sair() {
    limparSessao()
    navigate('/login', { replace: true })
  }

  if (estadoPerfil.tipo === 'carregando') {
    return (
      <main className="tela-laboratorio">
        <p>Carregando laboratorio...</p>
      </main>
    )
  }

  if (estadoPerfil.tipo === 'erro') {
    return (
      <main className="tela-laboratorio">
        <p role="alert" className="mensagem-erro">
          {estadoPerfil.mensagem}
        </p>
        <button type="button" onClick={carregarPerfil}>
          Tentar novamente
        </button>
      </main>
    )
  }

  const { professor, laboratorio, resumo } = estadoPerfil.perfil
  const semTreinador = resumo.treinadores === 0

  return (
    <main className="tela-laboratorio">
      <header>
        <h1>{laboratorio.nome}</h1>
        <p>Professor {professor.nome_exibicao ?? professor.usuario}</p>
        <Link to="/pokedex">Ver Pokedex</Link>
      </header>

      <dl className="resumo-laboratorio" aria-label="Resumo do laboratorio">
        <div>
          <dt>Nivel do laboratorio</dt>
          <dd>{laboratorio.nivel}</dd>
        </div>
        <div>
          <dt>Moedas</dt>
          <dd>{laboratorio.moedas}</dd>
        </div>
        <div>
          <dt>Pokemon</dt>
          <dd>{resumo.pokemon}</dd>
        </div>
        <div>
          <dt>Treinadores</dt>
          <dd>
            {resumo.treinadores} de {laboratorio.limite_treinadores}
          </dd>
        </div>
        <div>
          <dt>Locais desbloqueados</dt>
          <dd>{resumo.locais_desbloqueados}</dd>
        </div>
        <div>
          <dt>Pokedex</dt>
          <dd>
            {resumo.especies_capturadas} capturadas, {resumo.especies_vistas} vistas
          </dd>
        </div>
      </dl>

      {semTreinador && (
        <p className="aviso-vazio">
          Nenhum treinador no laboratorio. Recrute um para comecar a despachar expedicoes.
        </p>
      )}

      <section className="secao-acervo" aria-label="Acervo de Pokemon">
        <h2>Acervo</h2>
        <FiltrosPokemon valores={filtros} onMudar={aplicarFiltros} />

        <div className="acervo-layout">
          <div className="acervo-lista">
            {estadoLista.tipo === 'carregando' && <p>Carregando Pokemon...</p>}

            {estadoLista.tipo === 'erro' && (
              <div>
                <p role="alert" className="mensagem-erro">
                  {estadoLista.mensagem}
                </p>
                <button type="button" onClick={() => setTentativaLista((n) => n + 1)}>
                  Tentar novamente
                </button>
              </div>
            )}

            {estadoLista.tipo === 'pronto' && (
              <ListaPokemon
                itens={estadoLista.resposta.items}
                total={estadoLista.resposta.total}
                page={estadoLista.resposta.page}
                pageSize={estadoLista.resposta.page_size}
                selecionadoId={selecionadoId}
                onSelecionar={setSelecionadoId}
                onMudarPagina={mudarPagina}
              />
            )}
          </div>

          <FichaPokemon id={selecionadoId} onAtualizado={aoAtualizarApelido} />
        </div>
      </section>

      <section className="secao-mochila" aria-label="Mochila">
        <h2>Mochila</h2>

        {estadoItens.tipo === 'carregando' && <p>Carregando mochila...</p>}

        {estadoItens.tipo === 'erro' && (
          <div>
            <p role="alert" className="mensagem-erro">
              {estadoItens.mensagem}
            </p>
            <button type="button" onClick={carregarItens}>
              Tentar novamente
            </button>
          </div>
        )}

        {estadoItens.tipo === 'pronto' && <Mochila itens={estadoItens.itens} />}
      </section>

      <button type="button" onClick={sair}>
        Sair
      </button>
    </main>
  )
}
