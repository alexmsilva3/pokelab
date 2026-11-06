import type { TipoPokemon } from '@/api/tipos'
import { rotuloTipo } from '@/lib/tipos'

/** Selo de tipo de Pokemon, reaproveitado no cartao, na ficha e na Pokedex. */
export function RotuloTipo({ tipo }: { tipo: TipoPokemon }) {
  return <span className="rotulo rotulo-tipo">{rotuloTipo(tipo)}</span>
}
