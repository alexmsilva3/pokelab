import type { GanhoDeExperiencia, PokemonDoRelatorio } from '@/api/tipos'

export interface ExperienciasDoRelatorioProps {
  time: PokemonDoRelatorio[]
  treinador: GanhoDeExperiencia
  laboratorio: GanhoDeExperiencia
}

/**
 * As tres experiencias do relatorio de campo (spec 007, criterio 19): cada
 * Pokemon do time, o treinador e o laboratorio. Subida de nivel e evolucao
 * sao a parte boa da expedicao — por isso vem em destaque no resumo de cada
 * Pokemon ("nivel 5 para 7", e quando evoluiu "Bulbasaur virou Ivysaur"), nao
 * escondidas no meio da linha do tempo.
 */
export function ExperienciasDoRelatorio({
  time,
  treinador,
  laboratorio,
}: ExperienciasDoRelatorioProps) {
  return (
    <div className="experiencias-relatorio">
      <section aria-label="Experiencia do time">
        <h3>Time</h3>
        {time.length === 0 ? (
          <p className="aviso-vazio">Nenhum Pokemon participou desta expedicao.</p>
        ) : (
          <ul className="experiencias-relatorio-time">
            {time.map((pokemon) => (
              <li key={pokemon.pokemon_id} className="experiencias-relatorio-item">
                <span className="experiencias-relatorio-nome">{pokemon.especie_nome}</span>
                <span>
                  nivel {pokemon.nivel_antes} para {pokemon.nivel_depois}
                </span>
                <span>{pokemon.exp_ganha} exp</span>
                {pokemon.evoluiu_para_nome && (
                  <strong className="experiencias-relatorio-evolucao">
                    {pokemon.especie_nome} virou {pokemon.evoluiu_para_nome}
                  </strong>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-label="Experiencia do treinador">
        <h3>Treinador</h3>
        <p>
          Nivel {treinador.nivel_antes} para {treinador.nivel_depois} ({treinador.exp_ganha} exp)
        </p>
      </section>

      <section aria-label="Experiencia do laboratorio">
        <h3>Laboratorio</h3>
        <p>
          Nivel {laboratorio.nivel_antes} para {laboratorio.nivel_depois} (
          {laboratorio.exp_ganha} exp)
        </p>
      </section>
    </div>
  )
}
