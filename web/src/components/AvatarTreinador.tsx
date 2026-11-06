/**
 * Retrato do treinador sem arquivo: iniciais sobre uma cor, ambas derivadas
 * do nome pelo servidor (game/trainers.py::Avatar). Desenhado em CSS, nunca
 * buscado como imagem.
 */
import type { AvatarTreinador as AvatarTreinadorTipo } from '@/api/tipos'

export interface AvatarTreinadorProps {
  avatar: AvatarTreinadorTipo
  nome: string
}

export function AvatarTreinador({ avatar, nome }: AvatarTreinadorProps) {
  return (
    <span
      className="avatar-treinador"
      style={{ backgroundColor: avatar.cor }}
      role="img"
      aria-label={`Retrato de ${nome}`}
    >
      <span aria-hidden="true">{avatar.iniciais}</span>
    </span>
  )
}
