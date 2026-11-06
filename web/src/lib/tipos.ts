/**
 * Vocabulario de exibicao dos dezoito tipos de Pokemon. O servidor manda o
 * tipo em ingles, como esta no seed (species.json); aqui so se traduz o
 * rotulo mostrado na tela. Nao e regra de jogo nem dado de seed (Artigo V) —
 * e so o nome do mesmo jeito que "DISPONIVEL" vira "Disponivel" na tela do
 * treinador.
 */
import type { TipoPokemon } from '@/api/tipos'

const ROTULOS_TIPO: Record<TipoPokemon, string> = {
  normal: 'Normal',
  fire: 'Fogo',
  water: 'Agua',
  electric: 'Eletrico',
  grass: 'Planta',
  ice: 'Gelo',
  fighting: 'Lutador',
  poison: 'Veneno',
  ground: 'Terra',
  flying: 'Voador',
  psychic: 'Psiquico',
  bug: 'Inseto',
  rock: 'Pedra',
  ghost: 'Fantasma',
  dragon: 'Dragao',
  dark: 'Sombrio',
  steel: 'Aco',
  fairy: 'Fada',
}

export const TIPOS_POKEMON: TipoPokemon[] = Object.keys(ROTULOS_TIPO) as TipoPokemon[]

export function rotuloTipo(tipo: TipoPokemon): string {
  return ROTULOS_TIPO[tipo]
}
