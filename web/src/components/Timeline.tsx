import type { EventoDeExpedicao } from '@/api/tipos'
import { marcadorTipoEvento, rotuloTipoEvento } from '@/lib/relatorios'

export interface TimelineProps {
  eventos: EventoDeExpedicao[]
}

/**
 * Linha do tempo do relatorio de campo (spec 007, criterio 19). Lista
 * ordenada: a ORDEM e a que o servidor mandou no array, nunca reordenada por
 * `ocorrido_em_minuto` ou por qualquer outro criterio aqui (Artigo II, igual
 * ao que `Mapa.tsx` faz com a ordem dos locais).
 *
 * O marcador e so um caractere decorativo (`aria-hidden`); o tipo do evento
 * tambem vai em texto, porque leitor de tela nao ve cor nem simbolo.
 */
export function Timeline({ eventos }: TimelineProps) {
  if (eventos.length === 0) {
    return <p className="aviso-vazio">Nenhum evento registrado nesta expedicao.</p>
  }

  return (
    <ol className="timeline-relatorio">
      {eventos.map((evento) => (
        <li key={evento.ordem} className="timeline-relatorio-item">
          <span className="timeline-relatorio-minuto">{evento.ocorrido_em_minuto} min</span>
          <span className="timeline-relatorio-marcador" aria-hidden="true">
            {marcadorTipoEvento(evento.tipo)}
          </span>
          <span className="rotulo timeline-relatorio-tipo">{rotuloTipoEvento(evento.tipo)}</span>
          <span className="timeline-relatorio-texto">{evento.texto}</span>
        </li>
      ))}
    </ol>
  )
}
