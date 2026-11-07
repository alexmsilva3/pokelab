/**
 * Retrato do treinador.
 *
 * Duas camadas, e a de baixo nunca some: iniciais sobre uma cor, ambas
 * derivadas do nome pelo servidor (game/trainers.py::Avatar) e desenhadas em
 * CSS. Por cima, quando o servidor manda `sprite`, o retrato da classe de
 * treinador — que e um arquivo e portanto pode faltar.
 *
 * O sprite e `position: absolute` sobre as iniciais em vez de substitui-las:
 * se o acervo nao estiver montado (ver o mount de /sprites em main.py), a
 * imagem quebra e as iniciais continuam la embaixo, sem buraco na tela.
 */
import type { AvatarTreinador as AvatarTreinadorTipo } from '@/api/tipos'
import { urlSprite } from '@/api/client'

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
      {avatar.sprite && (
        <img
          className="avatar-treinador-sprite"
          src={urlSprite(avatar.sprite)}
          alt=""
          aria-hidden="true"
        />
      )}
    </span>
  )
}
