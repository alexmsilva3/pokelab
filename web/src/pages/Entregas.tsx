/**
 * Central de Entregas (spec 008, tarefa 17): a lista de pedidos, com prazo,
 * e os DOIS gestos distintos que `POST /deliveries/refresh` atende
 * (plan.md, "Prazo e reposicao"):
 *
 * - "Repor vagas" so aparece quando ha vaga aberta por expiracao ou por
 *   aceite (`vagas_para_repor > 0`) e NAO espera.
 * - "Regerar lista" so aparece quando a lista esta cheia de pedidos validos
 *   (`vagas_para_repor === 0`) e exige `INTERVALO_REGERAR_ENTREGAS` desde o
 *   ultimo sorteio — o contador mostra quanto falta, e o botao fica
 *   desabilitado ate chegar a zero.
 *
 * Os dois nunca aparecem juntos: misturar os rotulos faria o professor achar
 * que esta sendo punido por algo que nao fez. O contador de "Regerar lista"
 * e o contador de "Expira em" de cada pedido (`CartaoEntrega.tsx`) usam
 * rotulos diferentes de proposito, pelo mesmo motivo.
 */
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { listarEntregas, regerarEntregas } from '@/api/deliveries'
import type { RespostaEntregas } from '@/api/tipos'
import { CartaoEntrega } from '@/components/CartaoEntrega'
import { ContadorRegressivo } from '@/components/ContadorRegressivo'

type Estado =
  | { tipo: 'carregando' }
  | { tipo: 'erro'; mensagem: string }
  | { tipo: 'pronto'; resposta: RespostaEntregas }

export function Entregas() {
  const [estado, setEstado] = useState<Estado>({ tipo: 'carregando' })
  const [executando, setExecutando] = useState(false)
  const [erroRefresh, setErroRefresh] = useState<string | null>(null)

  const carregar = useCallback((sinal?: AbortSignal) => {
    setEstado({ tipo: 'carregando' })
    listarEntregas(sinal)
      .then((resposta) => setEstado({ tipo: 'pronto', resposta }))
      .catch((motivo: unknown) => {
        if (motivo instanceof DOMException && motivo.name === 'AbortError') return
        const mensagem =
          motivo instanceof ApiError
            ? motivo.message
            : 'Nao foi possivel carregar a Central de Entregas. Verifique a conexao.'
        setEstado({ tipo: 'erro', mensagem })
      })
  }, [])

  useEffect(() => {
    const controlador = new AbortController()
    carregar(controlador.signal)
    return () => controlador.abort()
  }, [carregar])

  /** Atualizacao silenciosa: usada pelos contadores e apos aceite/conclusao. */
  const atualizarSilenciosamente = useCallback(() => {
    listarEntregas()
      .then((resposta) => setEstado({ tipo: 'pronto', resposta }))
      .catch(() => {})
  }, [])

  async function executarRefresh() {
    setErroRefresh(null)
    setExecutando(true)
    try {
      const resposta = await regerarEntregas()
      setEstado({ tipo: 'pronto', resposta })
    } catch (motivo) {
      setErroRefresh(
        motivo instanceof ApiError ? motivo.message : 'Nao foi possivel atualizar os pedidos.',
      )
    } finally {
      setExecutando(false)
    }
  }

  if (estado.tipo === 'carregando') {
    return (
      <main className="tela-entregas">
        <p>Carregando Central de Entregas...</p>
      </main>
    )
  }

  if (estado.tipo === 'erro') {
    return (
      <main className="tela-entregas">
        <p role="alert" className="mensagem-erro">
          {estado.mensagem}
        </p>
        <button type="button" onClick={() => carregar()}>
          Tentar novamente
        </button>
      </main>
    )
  }

  const { items, vagas_para_repor: vagasParaRepor, segundos_para_regerar: segundosParaRegerar } =
    estado.resposta

  return (
    <main className="tela-entregas">
      <header>
        <h1>Central de Entregas</h1>
        <Link to="/laboratorio">Voltar ao laboratorio</Link>
      </header>

      {erroRefresh && (
        <p role="alert" className="mensagem-erro">
          {erroRefresh}
        </p>
      )}

      <div className="entregas-acoes">
        {vagasParaRepor > 0 && (
          <button type="button" className="botao-primario" disabled={executando} onClick={executarRefresh}>
            {executando ? 'Repondo...' : 'Repor vagas'}
          </button>
        )}

        {vagasParaRepor === 0 && (
          <p className="entregas-regerar">
            <button
              type="button"
              disabled={executando || segundosParaRegerar > 0}
              onClick={executarRefresh}
            >
              {executando ? 'Regerando...' : 'Regerar lista'}
            </button>
            {segundosParaRegerar > 0 && (
              <span>
                {' '}
                Disponivel em:{' '}
                <ContadorRegressivo
                  segundosRestantes={segundosParaRegerar}
                  aoChegarAZero={atualizarSilenciosamente}
                />
              </span>
            )}
          </p>
        )}
      </div>

      {items.length === 0 ? (
        <p className="aviso-vazio">
          Nenhum pedido ativo agora. Reponha as vagas para receber novos pedidos.
        </p>
      ) : (
        <ul className="lista-entregas" aria-label="Pedidos da Central de Entregas">
          {items.map((entrega) => (
            <li key={entrega.id}>
              <CartaoEntrega entrega={entrega} onAtualizar={atualizarSilenciosamente} />
            </li>
          ))}
        </ul>
      )}
    </main>
  )
}
