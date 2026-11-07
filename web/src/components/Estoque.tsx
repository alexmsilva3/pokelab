import type { CategoriaItem, ItemEmEstoque } from '@/api/tipos'

const ROTULOS_CATEGORIA: Record<CategoriaItem, string> = {
  POKEBOLA: 'Pokebolas',
  CURA: 'Cura',
  REVIVE: 'Revive',
}

const ORDEM_CATEGORIAS: CategoriaItem[] = ['POKEBOLA', 'CURA', 'REVIVE']

export interface EstoqueProps {
  itens: ItemEmEstoque[]
}

/**
 * Estoque de itens do laboratorio — nao confundir com a mochila que o
 * treinador leva numa expedicao (essa vive em `DespacharExpedicao`). Mesma
 * palavra para coisas diferentes ja causou confusao; "Estoque" e exclusivo
 * do que o laboratorio guarda.
 *
 * Agrupa por categoria e nunca mostra item com quantidade zero (regra 11 da
 * spec 003). O servidor ja nao manda item zerado, mas o filtro aqui e a
 * segunda linha de defesa, nao a primeira.
 */
export function Estoque({ itens }: EstoqueProps) {
  const visiveis = itens.filter((entrada) => entrada.quantidade > 0)

  if (visiveis.length === 0) {
    return (
      <p className="aviso-vazio">
        O estoque esta vazio. Conclua expedicoes ou entregas para repor.
      </p>
    )
  }

  return (
    <div className="estoque">
      {ORDEM_CATEGORIAS.map((categoria) => {
        const itensCategoria = visiveis.filter((entrada) => entrada.categoria === categoria)
        if (itensCategoria.length === 0) return null

        return (
          <section key={categoria} className="estoque-categoria">
            <h3>{ROTULOS_CATEGORIA[categoria]}</h3>
            <ul>
              {itensCategoria.map((entrada) => (
                <li key={entrada.item_id}>
                  <span>{entrada.nome}</span>
                  <span>{entrada.quantidade}</span>
                </li>
              ))}
            </ul>
          </section>
        )
      })}
    </div>
  )
}
