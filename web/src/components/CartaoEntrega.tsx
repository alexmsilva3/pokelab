/**
 * Cartao de um pedido da Central de Entregas (spec 008, tarefas 17 e 18). O
 * que o cartao mostra depende so do `estado_observado` que o servidor manda,
 * nunca do relogio local (Artigo II):
 *
 * - `DISPONIVEL`: requisitos (quantidade pedida e quanto o professor tem no
 *   viveiro), destino, duracao, recompensa e a contagem de quanto falta para
 *   VENCER. O botao "Aceitar" so aparece quando `atendivel`; senao, mostra o
 *   `motivo` que o servidor escreveu.
 * - `EXPIRADA`: o pedido venceu sem aceite (regra 16) e aparece como tal —
 *   nunca some em silencio (criterio 18).
 * - `EM_CURSO`: ja foi aceito; mostra quanto falta para o treinador voltar e
 *   o botao "Receber entrega", que reclama a conclusao assim que o prazo
 *   vencer (mesmo padrao do ADR-006 usado pela expedicao).
 * - `CONCLUIDA` / `DESCARTADA`: so o rotulo do estado.
 */
import { useRef, useState } from 'react'
import { ApiError } from '@/api/client'
import { concluirEntrega } from '@/api/deliveries'
import type { EntregaLer, ResultadoDeEntrega } from '@/api/tipos'
import { AceitarEntrega } from '@/components/AceitarEntrega'
import { ContadorRegressivo } from '@/components/ContadorRegressivo'
import { rotuloEstadoEntrega } from '@/lib/entregas'

export interface CartaoEntregaProps {
  entrega: EntregaLer
  /** Atualizacao silenciosa da lista: usada pelo prazo zerado e apos o aceite/conclusao. */
  onAtualizar: () => void
}

export function CartaoEntrega({ entrega, onAtualizar }: CartaoEntregaProps) {
  const [mostrarAceite, setMostrarAceite] = useState(false)
  const [concluindo, setConcluindo] = useState(false)
  const [erroConcluir, setErroConcluir] = useState<string | null>(null)
  const [resultado, setResultado] = useState<ResultadoDeEntrega | null>(null)
  const emVooRef = useRef(false)

  const disponivel = entrega.estado_observado === 'DISPONIVEL'
  const expirada = entrega.estado_observado === 'EXPIRADA'
  const emCurso = entrega.estado_observado === 'EM_CURSO'

  async function aoReceberEntrega() {
    if (emVooRef.current) return
    emVooRef.current = true
    setConcluindo(true)
    setErroConcluir(null)
    try {
      const resposta = await concluirEntrega(entrega.id)
      setResultado(resposta.resultado)
      onAtualizar()
    } catch (motivo) {
      setErroConcluir(
        motivo instanceof ApiError ? motivo.message : 'Nao foi possivel receber esta entrega.',
      )
      onAtualizar()
    } finally {
      emVooRef.current = false
      setConcluindo(false)
    }
  }

  function aoAceitar() {
    setMostrarAceite(false)
    onAtualizar()
  }

  return (
    <article className="cartao-entrega" aria-label={entrega.titulo}>
      <h3>{entrega.titulo}</h3>
      <p className="cartao-entrega-destino">Destino: {entrega.local_destino_nome}</p>
      <span className="rotulo">{rotuloEstadoEntrega(entrega.estado_observado)}</span>

      <ul className="entrega-requisitos" aria-label="Requisitos do pedido">
        {entrega.requisitos.map((requisito) => (
          <li key={requisito.especie_id}>
            {requisito.especie_nome}: {requisito.quantidade} pedidos, {requisito.disponiveis_no_viveiro}{' '}
            no viveiro
          </li>
        ))}
      </ul>

      {/*
        Nulo quando o pedido nao e atendivel hoje: sem Pokemon candidato no
        viveiro nao ha base para a previa, e "null min" ao lado do motivo da
        recusa seria um numero inventado onde o servidor nao calculou nenhum
        (mesmo cuidado de `PreviaExpedicao` em `DespacharExpedicao.tsx`).
      */}
      {entrega.duracao_minutos !== null && entrega.recompensa_moedas !== null && (
        <dl className="entrega-recompensas" aria-label="Duracao e recompensa">
          <div>
            <dt>Duracao</dt>
            <dd>{entrega.duracao_minutos} min</dd>
          </div>
          <div>
            <dt>Recompensa</dt>
            <dd>{entrega.recompensa_moedas} moedas</dd>
          </div>
        </dl>
      )}

      {disponivel && entrega.segundos_para_expirar !== null && (
        <p className="entrega-contador">
          Expira em:{' '}
          <ContadorRegressivo
            segundosRestantes={entrega.segundos_para_expirar}
            aoChegarAZero={onAtualizar}
          />
        </p>
      )}

      {expirada && (
        <p className="aviso-vazio">
          Este pedido venceu sem aceite e saiu de circulacao. Reponha as vagas para ver outro.
        </p>
      )}

      {disponivel && !entrega.atendivel && (
        <p className="mensagem-erro">{entrega.motivo}</p>
      )}

      {disponivel && entrega.atendivel && !mostrarAceite && (
        <button type="button" className="botao-primario" onClick={() => setMostrarAceite(true)}>
          Aceitar
        </button>
      )}

      {mostrarAceite && (
        <AceitarEntrega
          entrega={entrega}
          onAceito={aoAceitar}
          onCancelar={() => setMostrarAceite(false)}
        />
      )}

      {emCurso && entrega.segundos_restantes !== null && (
        <p className="entrega-contador">
          Retorna em:{' '}
          <ContadorRegressivo segundosRestantes={entrega.segundos_restantes} aoChegarAZero={onAtualizar} />
        </p>
      )}

      {erroConcluir && (
        <p role="alert" className="mensagem-erro">
          {erroConcluir}
        </p>
      )}

      {emCurso && (
        <button type="button" className="botao-primario" disabled={concluindo} onClick={aoReceberEntrega}>
          {concluindo ? 'Recebendo...' : 'Receber entrega'}
        </button>
      )}

      {resultado && (
        <dl className="entrega-resultado" aria-label="Resultado da entrega">
          <div>
            <dt>Pokemon entregues</dt>
            <dd>
              {resultado.pokemon_entregues
                .map((pokemon) => `${pokemon.especie_nome} (Nv. ${pokemon.nivel})`)
                .join(', ')}
            </dd>
          </div>
          <div>
            <dt>Moedas ganhas</dt>
            <dd>{resultado.moedas_ganhas}</dd>
          </div>
        </dl>
      )}
    </article>
  )
}
