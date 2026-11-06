import { CartaoPokemon } from '@/components/CartaoPokemon'
import type { PokemonResumo } from '@/api/tipos'

export interface ListaPokemonProps {
  itens: PokemonResumo[]
  total: number
  page: number
  pageSize: number
  selecionadoId: string | null
  onSelecionar: (id: string) => void
  onMudarPagina: (page: number) => void
}

export function ListaPokemon({
  itens,
  total,
  page,
  pageSize,
  selecionadoId,
  onSelecionar,
  onMudarPagina,
}: ListaPokemonProps) {
  const totalPaginas = Math.max(1, Math.ceil(total / pageSize))

  // Pagina vazia tem duas causas diferentes, e dizer "ajuste os filtros" na
  // segunda deixa o professor sem saida: a navegacao some junto com a lista e
  // nao ha como voltar para a pagina 1.
  if (itens.length === 0) {
    const passouDoFim = total > 0 && page > totalPaginas
    return (
      <div className="lista-vazia">
        <p className="aviso-vazio">
          {passouDoFim
            ? `Esta pagina nao existe: o acervo tem ${totalPaginas} ${
                totalPaginas === 1 ? 'pagina' : 'paginas'
              }.`
            : 'Nenhum Pokemon encontrado com esses filtros. Ajuste os filtros para ver outros resultados.'}
        </p>
        {passouDoFim && (
          <button type="button" onClick={() => onMudarPagina(1)}>
            Voltar para a primeira pagina
          </button>
        )}
      </div>
    )
  }
  const inicio = (page - 1) * pageSize + 1
  const fim = Math.min(total, page * pageSize)

  return (
    <div className="lista-pokemon">
      <ul className="lista-pokemon-grade">
        {itens.map((pokemon) => (
          <li key={pokemon.id}>
            <CartaoPokemon
              pokemon={pokemon}
              selecionado={pokemon.id === selecionadoId}
              onSelecionar={onSelecionar}
            />
          </li>
        ))}
      </ul>

      <nav className="paginacao" aria-label="Paginacao do acervo">
        <span>
          {inicio}-{fim} de {total}
        </span>
        <button type="button" onClick={() => onMudarPagina(page - 1)} disabled={page <= 1}>
          Anterior
        </button>
        <button
          type="button"
          onClick={() => onMudarPagina(page + 1)}
          disabled={page >= totalPaginas}
        >
          Proxima
        </button>
      </nav>
    </div>
  )
}
