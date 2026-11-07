/**
 * A barra de progresso do nivel.
 *
 * Substitui o texto "Faltam 44 de experiencia para o proximo nivel", que era
 * exato e nao dizia nada: 44 e muito ou pouco conforme o degrau custe 60 ou
 * 6000, e o professor nao tem como saber qual dos dois.
 *
 * Os numeros vem PRONTOS do servidor (`experiencia_vencida_no_nivel` e
 * `experiencia_do_nivel`). O componente so divide um pelo outro — calcular o
 * degrau aqui exigiria as curvas de crescimento, que sao regra de jogo
 * (Artigo II).
 *
 * Desenhada em CSS, sem animacao: a interface e lista-e-botao, e uma barra que
 * desliza ao carregar e enfeite que custa quadro.
 */
import type { PokemonDetalhe } from '@/api/tipos'

export interface BarraDeExperienciaProps {
  detalhe: Pick<
    PokemonDetalhe,
    | 'nivel'
    | 'nivel_maximo'
    | 'experiencia_vencida_no_nivel'
    | 'experiencia_do_nivel'
    | 'experiencia_para_proximo_nivel'
  >
}

/** Entre 0 e 100. Degrau de tamanho zero so acontece no nivel maximo: cheio. */
function porcentagem({
  experiencia_vencida_no_nivel: vencida,
  experiencia_do_nivel: tamanho,
}: BarraDeExperienciaProps['detalhe']): number {
  if (tamanho <= 0) return 100
  return Math.min(100, Math.max(0, Math.round((vencida / tamanho) * 100)))
}

export function BarraDeExperiencia({ detalhe }: BarraDeExperienciaProps) {
  const pct = porcentagem(detalhe)
  const texto = detalhe.nivel_maximo
    ? 'Nivel maximo atingido.'
    : `${detalhe.experiencia_vencida_no_nivel} de ${detalhe.experiencia_do_nivel} ` +
      `para o nivel ${detalhe.nivel + 1}. Faltam ${detalhe.experiencia_para_proximo_nivel}.`

  return (
    <div className="barra-exp">
      {/*
        role="progressbar" com os tres aria-value*: e assim que leitor de tela
        anuncia "40 por cento". O texto abaixo continua existindo porque o
        numero exato importa para quem planeja a proxima expedicao — a barra da
        a nocao, o texto da a conta.
      */}
      <div
        className="barra-exp-trilho"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Experiencia do nivel ${detalhe.nivel}`}
      >
        <div className="barra-exp-preenchida" style={{ width: `${pct}%` }} />
      </div>
      <p className="barra-exp-texto">{texto}</p>
    </div>
  )
}
