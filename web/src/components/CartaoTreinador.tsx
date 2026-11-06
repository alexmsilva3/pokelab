import type { TreinadorResumo } from '@/api/tipos'
import { AvatarTreinador } from '@/components/AvatarTreinador'
import { SpritePokemon } from '@/components/SpritePokemon'
import { rotuloStatus } from '@/lib/treinadores'

export interface CartaoTreinadorProps {
  treinador: TreinadorResumo
  selecionado?: boolean
  onSelecionar: (id: string) => void
}

/**
 * Um treinador sem Pokemon e estado normal (regra 10, SDD) — e como todos
 * comecam. O texto convida a montar o time em vez de soar como erro.
 */
export function CartaoTreinador({
  treinador,
  selecionado = false,
  onSelecionar,
}: CartaoTreinadorProps) {
  return (
    <button
      type="button"
      className="cartao-treinador"
      aria-pressed={selecionado}
      onClick={() => onSelecionar(treinador.id)}
    >
      <AvatarTreinador avatar={treinador.avatar} nome={treinador.nome} />
      <span className="cartao-treinador-nome">{treinador.nome}</span>
      <span className="rotulo">{rotuloStatus(treinador.status)}</span>
      <span className="cartao-treinador-nivel">Nv. {treinador.nivel}</span>

      {treinador.time.length === 0 ? (
        <p className="aviso-vazio">Sem Pokemon no time. Monte o time para despachar expedicoes.</p>
      ) : (
        <ul className="cartao-treinador-time" aria-label={`Time de ${treinador.nome}`}>
          {treinador.time.map((pokemon) => (
            <li key={pokemon.id}>
              <SpritePokemon caminho={pokemon.sprite} nome={pokemon.nome} />
            </li>
          ))}
        </ul>
      )}

      <span className="cartao-treinador-capacidade">
        Bagagem: {treinador.capacidade_bagagem}{' '}
        {treinador.capacidade_bagagem === 1 ? 'vaga' : 'vagas'}
      </span>
    </button>
  )
}
