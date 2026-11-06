import type { EntradaPokedex } from '@/api/tipos'
import { RotuloTipo } from '@/components/RotuloTipo'
import { SpritePokemon } from '@/components/SpritePokemon'

/**
 * As tres aparencias da Pokedex (regras 9 e 10 da spec 003). Uma entrada
 * DESCONHECIDA nao recebe nome nem tipo como prop: o servidor nunca manda
 * esses campos para ela, entao nao ha como este componente inventa-los.
 */
export function CartaoPokedex({ entrada }: { entrada: EntradaPokedex }) {
  if (entrada.estado === 'DESCONHECIDA') {
    return (
      <li className="cartao-pokedex cartao-pokedex--desconhecida">
        <SpritePokemon caminho={null} nome={null} numero={entrada.numero} />
      </li>
    )
  }

  return (
    <li className="cartao-pokedex">
      <SpritePokemon caminho={entrada.sprite} nome={entrada.nome} numero={entrada.numero} />
      <span className="cartao-pokedex-numero">#{entrada.numero}</span>
      <span className="cartao-pokedex-nome">{entrada.nome}</span>
      <span className="cartao-pokedex-tipos">
        {entrada.tipos.map((tipo) => (
          <RotuloTipo key={tipo} tipo={tipo} />
        ))}
      </span>
      {entrada.estado === 'CAPTURADA' ? (
        <span className="rotulo rotulo-capturada">Capturada ({entrada.quantidade})</span>
      ) : (
        <span className="rotulo rotulo-vista">Nao capturada</span>
      )}
    </li>
  )
}
