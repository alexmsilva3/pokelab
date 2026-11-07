import type { ItemDoRelatorio } from '@/api/tipos'

export interface ItensDoRelatorioProps {
  consumidos: ItemDoRelatorio[]
  encontrados: ItemDoRelatorio[]
}

/** Itens consumidos e encontrados no relatorio de campo (spec 007, criterio 19). */
export function ItensDoRelatorio({ consumidos, encontrados }: ItensDoRelatorioProps) {
  if (consumidos.length === 0 && encontrados.length === 0) {
    return <p className="aviso-vazio">Nenhum item consumido ou encontrado nesta expedicao.</p>
  }

  return (
    <div className="itens-relatorio">
      <section aria-label="Itens consumidos">
        <h3>Consumidos</h3>
        {consumidos.length === 0 ? (
          <p className="aviso-vazio">Nenhum item consumido.</p>
        ) : (
          <ul>
            {consumidos.map((item) => (
              <li key={item.item_id}>
                <span>{item.nome}</span>
                <span>{item.quantidade}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-label="Itens encontrados">
        <h3>Encontrados</h3>
        {encontrados.length === 0 ? (
          <p className="aviso-vazio">Nenhum item encontrado.</p>
        ) : (
          <ul>
            {encontrados.map((item) => (
              <li key={item.item_id}>
                <span>{item.nome}</span>
                <span>{item.quantidade}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
