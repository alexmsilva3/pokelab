import type { EspecieAvistada } from '@/api/tipos'
import { SpritePokemon } from '@/components/SpritePokemon'

export interface EspeciesAvistadasProps {
  especies: EspecieAvistada[]
}

/**
 * As especies que o laboratorio ja avistou num local (spec 005, criterios 8 e
 * 9). Uma lista vazia e um local nunca visitado — e nunca mostra quantas
 * especies existem ali (regra 10): nao ha "0 de 6", so o convite para mandar
 * um treinador descobrir.
 */
export function EspeciesAvistadas({ especies }: EspeciesAvistadasProps) {
  if (especies.length === 0) {
    return (
      <p className="aviso-vazio">
        Nenhum Pokemon avistado aqui ainda. Mande um treinador para descobrir o que mora neste
        lugar.
      </p>
    )
  }

  return (
    <ul className="lista-especies-avistadas" aria-label="Especies avistadas neste local">
      {especies.map((especie) => (
        <li key={especie.especie_id}>
          <SpritePokemon caminho={especie.sprite} nome={especie.nome} />
          <span className="especie-avistada-nome">{especie.nome}</span>
          <span className="especie-avistada-vezes">
            {especie.vezes_visto === 1 ? 'Avistado 1 vez' : `Avistado ${especie.vezes_visto} vezes`}
          </span>
        </li>
      ))}
    </ul>
  )
}
