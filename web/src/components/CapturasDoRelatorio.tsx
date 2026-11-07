import type { CapturaDoRelatorio } from '@/api/tipos'

export interface CapturasDoRelatorioProps {
  capturas: CapturaDoRelatorio[]
}

/**
 * Capturas do relatorio de campo (spec 007, criterio 19): o que veio junto,
 * com especie e nivel. O contrato do endpoint (plan.md, "Contratos de API")
 * nao manda sprite nesta lista — so `especie_id`, `especie_nome`, `nivel` e
 * `pokemon_id` — e esta tela nao inventa campo que o servidor nao envia.
 */
export function CapturasDoRelatorio({ capturas }: CapturasDoRelatorioProps) {
  if (capturas.length === 0) {
    return (
      <p className="aviso-vazio">
        Nenhuma captura nesta expedicao. Leve Pokebolas e deixe espaco na bagagem na proxima.
      </p>
    )
  }

  return (
    <ul className="capturas-relatorio">
      {capturas.map((captura) => (
        <li key={captura.pokemon_id} className="capturas-relatorio-item">
          <span className="capturas-relatorio-nome">{captura.especie_nome}</span>
          <span className="capturas-relatorio-nivel">Nv. {captura.nivel}</span>
        </li>
      ))}
    </ul>
  )
}
