/**
 * Contagem regressiva de expedicao (spec 006, tarefa 10).
 *
 * O PONTO DELICADO: este componente conta localmente, segundo a segundo, para
 * nao bater no servidor a cada tique — mas o servidor e a autoridade (Artigo
 * II). Toda vez que `segundosRestantes` muda (um novo poll), a contagem local
 * se CORRIGE para o valor recebido; ela nunca guarda um prazo e conta sozinha
 * ate o fim, porque um relogio de cliente adiantado concluiria a expedicao
 * antes do servidor.
 *
 * Ao chegar a zero, o componente NAO declara a expedicao terminada por conta
 * propria: so avisa `aoChegarAZero`, e quem chama consulta o servidor e
 * mostra o `estado_observado` que ele devolver.
 *
 * O intervalo de um segundo e pausado quando a aba esta oculta
 * (document.visibilityState): contar em segundo plano e desperdicio, e o
 * proximo poll corrige qualquer atraso de qualquer forma.
 */
import { useEffect, useRef, useState } from 'react'
import { formatarTempoRestante } from '@/lib/expedicoes'

export interface ContadorRegressivoProps {
  /** Autoridade do servidor: cada poll traz um novo valor e corrige a contagem local. */
  segundosRestantes: number
  /** Avisa uma unica vez quando a contagem local chega a zero. */
  aoChegarAZero?: () => void
}

export function ContadorRegressivo({ segundosRestantes, aoChegarAZero }: ContadorRegressivoProps) {
  const [segundosLocais, setSegundosLocais] = useState(segundosRestantes)
  const avisadoRef = useRef(false)

  // Correcao pelo servidor: todo novo valor de `segundosRestantes` substitui
  // a contagem local, nunca a complementa. Um valor positivo novo (por
  // exemplo, a mesma expedicao vista de novo apos reabrir a aba) reabilita o
  // aviso de zero para o proximo ciclo.
  useEffect(() => {
    setSegundosLocais(segundosRestantes)
    if (segundosRestantes > 0) avisadoRef.current = false
  }, [segundosRestantes])

  // Um unico intervalo de um segundo. Ele nao reconta por conta propria o
  // prazo da expedicao: so decrementa a exibicao local entre polls, e para em
  // zero sem nunca passar de zero (nunca negativo).
  useEffect(() => {
    const id = window.setInterval(() => {
      if (document.visibilityState !== 'visible') return
      setSegundosLocais((atual) => (atual > 0 ? atual - 1 : 0))
    }, 1000)
    return () => window.clearInterval(id)
  }, [])

  useEffect(() => {
    if (segundosLocais <= 0 && !avisadoRef.current) {
      avisadoRef.current = true
      aoChegarAZero?.()
    }
  }, [segundosLocais, aoChegarAZero])

  // Rotulo acessivel estavel: atualiza por minuto, nao a cada segundo, para
  // nao inundar leitor de tela com `aria-live`.
  const minutosRestantes = Math.ceil(segundosLocais / 60)
  const rotuloAcessivel =
    segundosLocais <= 0
      ? 'Prazo encerrado. Consultando o servidor.'
      : minutosRestantes === 1
        ? 'Cerca de 1 minuto restante'
        : `Cerca de ${minutosRestantes} minutos restantes`

  return (
    <span className="contador-regressivo">
      <span aria-hidden="true">{formatarTempoRestante(segundosLocais)}</span>
      <span className="apenas-leitor" aria-live="polite">
        {rotuloAcessivel}
      </span>
    </span>
  )
}
