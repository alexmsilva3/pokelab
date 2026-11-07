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
        O numero exato aparece ao passar o mouse, para a ficha nao carregar uma
        linha de texto o tempo todo. Mas hover sozinho exclui gente: em tela de
        toque nao existe, e quem navega por teclado nunca passa por cima de
        nada. Por isso o trilho e focalizavel (`tabIndex`) e o CSS mostra o
        texto tambem em `:focus-visible` e `:focus-within`.

        E o texto continua na arvore de acessibilidade pelo `aria-label`: para
        leitor de tela ele nunca esteve escondido, porque esconder o numero de
        quem nao ve a barra seria esconder a informacao inteira.
      */}
      <div
        className="barra-exp-trilho"
        role="progressbar"
        tabIndex={0}
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuetext={texto}
        aria-label={`Experiencia do nivel ${detalhe.nivel}`}
      >
        <div className="barra-exp-preenchida" style={{ width: `${pct}%` }} />
      </div>
      <p className="barra-exp-texto" aria-hidden="true">
        {texto}
      </p>
    </div>
  )
}
