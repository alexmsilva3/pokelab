import type { TipoPokemon } from '@/api/tipos'
import { rotuloTipo, TIPOS_POKEMON } from '@/lib/tipos'

export interface ValoresFiltroPokemon {
  tipo?: TipoPokemon
  nivelMin?: number
  nivelMax?: number
  /** undefined = qualquer; true = so com treinador; false = so no laboratorio. */
  atribuido?: boolean
}

export interface FiltrosPokemonProps {
  valores: ValoresFiltroPokemon
  onMudar: (valores: ValoresFiltroPokemon) => void
}

/**
 * Os filtros combinam entre si (regra 3 da spec 003): cada campo muda uma
 * chave e preserva as demais. Quem decide o resultado e o servidor — aqui so
 * se monta o criterio que ele vai receber.
 */
const NIVEL_MINIMO = 1
const NIVEL_MAXIMO = 100

/**
 * Converte o que foi digitado num nivel valido, ou em nenhum filtro.
 *
 * O atributo `min` do input e so dica visual: o navegador deixa digitar 0, e
 * o servidor recusa com 422. O resultado era a lista inteira sumir atras de
 * uma mensagem de erro por causa de uma tecla.
 */
function nivelDigitado(valor: string): number | undefined {
  if (valor === '') return undefined
  const numero = Number(valor)
  if (!Number.isInteger(numero)) return undefined
  if (numero < NIVEL_MINIMO) return NIVEL_MINIMO
  if (numero > NIVEL_MAXIMO) return NIVEL_MAXIMO
  return numero
}

export function FiltrosPokemon({ valores, onMudar }: FiltrosPokemonProps) {
  return (
    <form
      className="filtros-pokemon"
      aria-label="Filtros do acervo"
      onSubmit={(evento) => evento.preventDefault()}
    >
      <div>
        <label htmlFor="filtro-tipo">Tipo</label>
        <select
          id="filtro-tipo"
          value={valores.tipo ?? ''}
          onChange={(evento) => {
            const valor = evento.target.value as TipoPokemon | ''
            onMudar({ ...valores, tipo: valor === '' ? undefined : valor })
          }}
        >
          <option value="">Qualquer tipo</option>
          {TIPOS_POKEMON.map((tipo) => (
            <option key={tipo} value={tipo}>
              {rotuloTipo(tipo)}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="filtro-nivel-min">Nivel minimo</label>
        <input
          id="filtro-nivel-min"
          type="number"
          min={1}
          max={100}
          value={valores.nivelMin ?? ''}
          onChange={(evento) => {
            onMudar({ ...valores, nivelMin: nivelDigitado(evento.target.value) })
          }}
        />
      </div>

      <div>
        <label htmlFor="filtro-nivel-max">Nivel maximo</label>
        <input
          id="filtro-nivel-max"
          type="number"
          min={1}
          max={100}
          value={valores.nivelMax ?? ''}
          onChange={(evento) => {
            onMudar({ ...valores, nivelMax: nivelDigitado(evento.target.value) })
          }}
        />
      </div>

      <div>
        <label htmlFor="filtro-atribuicao">Atribuicao</label>
        <select
          id="filtro-atribuicao"
          value={valores.atribuido === undefined ? '' : String(valores.atribuido)}
          onChange={(evento) => {
            const valor = evento.target.value
            onMudar({
              ...valores,
              atribuido: valor === '' ? undefined : valor === 'true',
            })
          }}
        >
          <option value="">Qualquer</option>
          <option value="false">No laboratorio</option>
          <option value="true">Com treinador</option>
        </select>
      </div>
    </form>
  )
}
