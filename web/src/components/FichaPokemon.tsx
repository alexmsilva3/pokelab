/**
 * Painel lateral de detalhe (plan.md): o professor compara Pokemon de uma
 * lista, entao a ficha nunca e rota propria — perder a lista a cada clique
 * atrapalharia exatamente isso.
 */
import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { atualizarApelido, buscarPokemon } from '@/api/pokemon'
import { ApiError } from '@/api/client'
import type { OrigemPokemon, PokemonDetalhe } from '@/api/tipos'
import { RotuloTipo } from '@/components/RotuloTipo'
import { BarraDeExperiencia } from '@/components/BarraDeExperiencia'
import { SpritePokemon } from '@/components/SpritePokemon'

export interface FichaPokemonProps {
  id: string | null
  /** Avisa o pai para refletir o apelido salvo tambem na lista. */
  onAtualizado?: (detalhe: PokemonDetalhe) => void
}

type Estado =
  | { tipo: 'vazio' }
  | { tipo: 'carregando' }
  | { tipo: 'erro'; mensagem: string }
  | { tipo: 'pronto'; detalhe: PokemonDetalhe }

function rotuloOrigem(origem: OrigemPokemon): string {
  if (origem === 'INICIAL') return 'Starter do kit inicial'
  if (origem === 'EVOLUCAO') return 'Evoluiu no laboratorio'
  return 'Capturado em campo'
}

function formatarData(dataIso: string | null): string {
  if (!dataIso) return 'Nao se aplica'
  return new Date(dataIso).toLocaleDateString('pt-BR')
}

/**
 * O apelido gravado, ou string vazia quando nao ha.
 *
 * Usa o campo cru que o servidor manda. Deduzir comparando `nome` com
 * `especie_nome` errava justamente quem apelida um Pidgey de "Pidgey": o campo
 * aparecia vazio e o proximo salvar apagava o apelido.
 */
function apelidoAtual(detalhe: PokemonDetalhe): string {
  return detalhe.apelido ?? ''
}

export function FichaPokemon({ id, onAtualizado }: FichaPokemonProps) {
  const [estado, setEstado] = useState<Estado>(id ? { tipo: 'carregando' } : { tipo: 'vazio' })
  const [apelidoCampo, setApelidoCampo] = useState('')
  const [salvando, setSalvando] = useState(false)
  const [erroApelido, setErroApelido] = useState<string | null>(null)

  const carregar = useCallback((idAtual: string, sinal?: AbortSignal) => {
    setEstado({ tipo: 'carregando' })
    buscarPokemon(idAtual, sinal)
      .then((detalhe) => {
        setEstado({ tipo: 'pronto', detalhe })
        setApelidoCampo(apelidoAtual(detalhe))
      })
      .catch((motivo: unknown) => {
        if (motivo instanceof DOMException && motivo.name === 'AbortError') return
        const mensagem =
          motivo instanceof ApiError
            ? motivo.message
            : 'Nao foi possivel carregar a ficha. Verifique a conexao.'
        setEstado({ tipo: 'erro', mensagem })
      })
  }, [])

  useEffect(() => {
    // Trocar de Pokemon zera o erro de gravacao: um alerta sobre o apelido do
    // Pokemon anterior continuava visivel na ficha do seguinte, parecendo que
    // o salvamento deste e que tinha falhado.
    setErroApelido(null)

    if (!id) {
      setEstado({ tipo: 'vazio' })
      return
    }
    const controlador = new AbortController()
    carregar(id, controlador.signal)
    return () => controlador.abort()
  }, [id, carregar])

  if (estado.tipo === 'vazio') {
    return (
      <aside className="ficha-pokemon" aria-label="Ficha do Pokemon">
        <p className="aviso-vazio">Selecione um Pokemon na lista para ver a ficha.</p>
      </aside>
    )
  }

  if (estado.tipo === 'carregando') {
    return (
      <aside className="ficha-pokemon" aria-label="Ficha do Pokemon">
        <p>Carregando ficha...</p>
      </aside>
    )
  }

  if (estado.tipo === 'erro') {
    return (
      <aside className="ficha-pokemon" aria-label="Ficha do Pokemon">
        <p role="alert" className="mensagem-erro">
          {estado.mensagem}
        </p>
        <button type="button" onClick={() => id && carregar(id)}>
          Tentar novamente
        </button>
      </aside>
    )
  }

  const { detalhe } = estado

  async function salvarApelido(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (!id) return

    setErroApelido(null)
    setSalvando(true)
    const valor = apelidoCampo.trim()

    try {
      const atualizado = await atualizarApelido(id, valor === '' ? null : valor)
      setEstado({ tipo: 'pronto', detalhe: atualizado })
      setApelidoCampo(apelidoAtual(atualizado))
      onAtualizado?.(atualizado)
    } catch (motivo) {
      setErroApelido(
        motivo instanceof ApiError ? motivo.message : 'Nao foi possivel salvar o apelido.',
      )
    } finally {
      setSalvando(false)
    }
  }

  return (
    <aside className="ficha-pokemon" aria-label={`Ficha de ${detalhe.nome}`}>
      <SpritePokemon caminho={detalhe.sprite} nome={detalhe.nome} tamanho="grande" />
      <h2>{detalhe.nome}</h2>
      <p className="ficha-pokemon-tipos">
        <RotuloTipo tipo={detalhe.tipo_primario} />
        {detalhe.tipo_secundario && <RotuloTipo tipo={detalhe.tipo_secundario} />}
      </p>

      <dl className="ficha-pokemon-stats" aria-label="Atributos no nivel atual">
        <div>
          <dt>Nivel</dt>
          <dd>{detalhe.nivel}</dd>
        </div>
        <div>
          <dt>HP</dt>
          <dd>
            {detalhe.hp_atual} / {detalhe.hp_maximo}
          </dd>
        </div>
        <div>
          <dt>Ataque</dt>
          <dd>{detalhe.stats.ataque}</dd>
        </div>
        <div>
          <dt>Defesa</dt>
          <dd>{detalhe.stats.defesa}</dd>
        </div>
        <div>
          <dt>Ataque especial</dt>
          <dd>{detalhe.stats.ataque_especial}</dd>
        </div>
        <div>
          <dt>Defesa especial</dt>
          <dd>{detalhe.stats.defesa_especial}</dd>
        </div>
        <div>
          <dt>Velocidade</dt>
          <dd>{detalhe.stats.velocidade}</dd>
        </div>
      </dl>

      <BarraDeExperiencia detalhe={detalhe} />

      <dl className="ficha-pokemon-origem">
        <div>
          <dt>Origem</dt>
          <dd>{rotuloOrigem(detalhe.origem)}</dd>
        </div>
        <div>
          <dt>Local de captura</dt>
          <dd>{detalhe.local_captura ?? 'Nao se aplica'}</dd>
        </div>
        <div>
          <dt>Chegou em</dt>
          <dd>{formatarData(detalhe.capturado_em)}</dd>
        </div>
      </dl>

      <form onSubmit={salvarApelido} className="ficha-pokemon-apelido">
        <label htmlFor="ficha-apelido">Apelido</label>
        <input
          id="ficha-apelido"
          value={apelidoCampo}
          maxLength={50}
          placeholder={detalhe.especie_nome}
          onChange={(evento) => setApelidoCampo(evento.target.value)}
        />
        <p className="ficha-pokemon-apelido-dica">Deixe em branco para usar o nome da especie.</p>
        {erroApelido && (
          <p role="alert" className="mensagem-erro">
            {erroApelido}
          </p>
        )}
        <button type="submit" className="botao-primario" disabled={salvando}>
          {salvando ? 'Salvando...' : 'Salvar apelido'}
        </button>
      </form>
    </aside>
  )
}
