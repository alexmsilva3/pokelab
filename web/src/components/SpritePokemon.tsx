/**
 * Imagem de um individuo ou especie, ou a silhueta quando o servidor nao
 * manda sprite nenhum (especie nunca vista na Pokedex). O caminho vem
 * relativo (ex.: "25-front.png") e a URL e montada pela propria API
 * (Artigo V e criterio 12: nenhuma imagem de servico externo).
 */
import { urlSprite } from '@/api/client'

export interface SpritePokemonProps {
  /** Nulo quando a especie ainda nao foi vista: nao ha imagem para mostrar. */
  caminho: string | null
  /** Nome usado no alt. Nulo junto com `caminho` null vira a silhueta. */
  nome: string | null
  /** Mostrado dentro da silhueta, quando disponivel (ex.: numero da Pokedex). */
  numero?: number
  tamanho?: 'pequena' | 'grande'
}

export function SpritePokemon({
  caminho,
  nome,
  numero,
  tamanho = 'pequena',
}: SpritePokemonProps) {
  const classeTamanho = tamanho === 'grande' ? 'sprite-pokemon--grande' : 'sprite-pokemon--pequena'

  if (!caminho || !nome) {
    const rotulo =
      numero !== undefined
        ? `Especie numero ${numero}, ainda nao avistada`
        : 'Especie ainda nao avistada'

    return (
      <div
        className={`sprite-pokemon sprite-pokemon--desconhecida ${classeTamanho}`}
        role="img"
        aria-label={rotulo}
      >
        {numero !== undefined && <span aria-hidden="true">#{numero}</span>}
      </div>
    )
  }

  return (
    <img
      className={`sprite-pokemon ${classeTamanho}`}
      src={urlSprite(caminho)}
      alt={nome}
      loading="lazy"
    />
  )
}
