import type { LocalNoMapa } from '@/api/tipos'
import { rotuloEstadoLocal, rotuloTipoLocal } from '@/lib/mapa'

export interface CartaoLocalProps {
  local: LocalNoMapa
  selecionado?: boolean
  onSelecionar: (id: string) => void
}

/**
 * Cartao de um local na lista do mapa (spec 005, criterios 1 a 4). O estado
 * vai em texto, nao so em cor, para quem usa leitor de tela. Alcancavel
 * mostra de onde a ida partiria e quanto tempo leva; fora de alcance mostra o
 * que falta visitar primeiro — e nunca os dois ao mesmo tempo, porque um
 * local nunca e as duas coisas.
 */
export function CartaoLocal({ local, selecionado = false, onSelecionar }: CartaoLocalProps) {
  const classeEstado = `rotulo-estado-${local.estado.toLowerCase().replace(/_/g, '-')}`

  return (
    <button
      type="button"
      className="cartao-local"
      aria-pressed={selecionado}
      onClick={() => onSelecionar(local.id)}
    >
      <span className="cartao-local-nome">{local.nome}</span>
      <span className="rotulo cartao-local-tipo">{rotuloTipoLocal(local.tipo)}</span>
      <span className={`rotulo ${classeEstado}`}>{rotuloEstadoLocal(local.estado)}</span>

      {local.estado === 'ALCANCAVEL' &&
        local.origem_nome !== null &&
        local.duracao_estimada_minutos !== null && (
          <p className="cartao-local-info">
            De {local.origem_nome}, {local.duracao_estimada_minutos} min
          </p>
        )}

      {local.estado === 'FORA_DE_ALCANCE' && (
        <p className="cartao-local-info">
          {local.proximo_passo_nome
            ? `Visite ${local.proximo_passo_nome} antes.`
            : 'Ainda nao ha caminho conhecido ate aqui.'}
        </p>
      )}
    </button>
  )
}
