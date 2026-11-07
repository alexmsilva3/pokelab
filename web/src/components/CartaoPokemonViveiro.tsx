/**
 * Uma linha do viveiro (spec 008, tarefa 16): sprite, nome e nivel, mais o
 * botao de soltar. A confirmacao nomeando o Pokemon e a chamada a API ficam
 * com quem monta a lista (`pages/Viveiro.tsx`) — este componente so exibe e
 * repassa o clique, do mesmo jeito que `CartaoExpedicao` repassa `onAbortar`.
 */
import type { PokemonResumo } from '@/api/tipos'
import { SpritePokemon } from '@/components/SpritePokemon'

export interface CartaoPokemonViveiroProps {
  pokemon: PokemonResumo
  soltando: boolean
  onSoltar: () => void
}

export function CartaoPokemonViveiro({ pokemon, soltando, onSoltar }: CartaoPokemonViveiroProps) {
  return (
    <article className="cartao-viveiro" aria-label={`${pokemon.nome}, nivel ${pokemon.nivel}`}>
      <SpritePokemon caminho={pokemon.sprite} nome={pokemon.nome} />
      <span className="cartao-viveiro-nome">{pokemon.nome}</span>
      <span className="cartao-viveiro-nivel">Nv. {pokemon.nivel}</span>
      <button type="button" className="botao-perigo" disabled={soltando} onClick={onSoltar}>
        {soltando ? 'Soltando...' : 'Soltar'}
      </button>
    </article>
  )
}
