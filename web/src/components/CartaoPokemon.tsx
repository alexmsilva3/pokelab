import { RotuloTipo } from '@/components/RotuloTipo'
import { SpritePokemon } from '@/components/SpritePokemon'
import type { PokemonResumo } from '@/api/tipos'

export interface CartaoPokemonProps {
  pokemon: PokemonResumo
  selecionado?: boolean
  onSelecionar: (id: string) => void
}

/**
 * `pokemon.nome` ja vem resolvido do servidor (apelido ou nome da especie,
 * regra 4 da spec 003) — o cartao so exibe, nao decide.
 */
export function CartaoPokemon({ pokemon, selecionado = false, onSelecionar }: CartaoPokemonProps) {
  return (
    <button
      type="button"
      className="cartao-pokemon"
      aria-pressed={selecionado}
      onClick={() => onSelecionar(pokemon.id)}
    >
      <SpritePokemon caminho={pokemon.sprite} nome={pokemon.nome} />
      <span className="cartao-pokemon-nome">{pokemon.nome}</span>
      <span className="cartao-pokemon-tipos">
        <RotuloTipo tipo={pokemon.tipo_primario} />
        {pokemon.tipo_secundario && <RotuloTipo tipo={pokemon.tipo_secundario} />}
      </span>
      <span className="cartao-pokemon-nivel">Nv. {pokemon.nivel}</span>
      {pokemon.atribuido && <span className="rotulo rotulo-treinador">Com treinador</span>}
    </button>
  )
}
