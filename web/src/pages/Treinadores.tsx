import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { listarTreinadores } from '@/api/trainers'
import type { RespostaTreinadores } from '@/api/tipos'
import { CartaoTreinador } from '@/components/CartaoTreinador'
import { MontarTime } from '@/components/MontarTime'

const MENSAGEM_ALTERACOES_PENDENTES =
  'Ha alteracoes no time que ainda nao foram salvas. Sair assim mesmo?'

type Estado =
  | { tipo: 'carregando' }
  | { tipo: 'erro'; mensagem: string }
  | { tipo: 'pronto'; resposta: RespostaTreinadores }

export function Treinadores() {
  const [estado, setEstado] = useState<Estado>({ tipo: 'carregando' })
  const [selecionadoId, setSelecionadoId] = useState<string | null>(null)
  const [temPendencias, setTemPendencias] = useState(false)

  /**
   * Troca o treinador aberto, confirmando antes se ha time montado e nao salvo.
   *
   * O aviso mora aqui e nao no painel porque `MontarTime` e remontado por
   * `key` a cada troca: o confirm interno do botao Fechar nunca chegava a
   * rodar nesse caminho, e a composicao pendente sumia sem uma palavra.
   */
  function trocarSelecao(id: string) {
    const proximo = id === selecionadoId ? null : id
    if (temPendencias && !window.confirm(MENSAGEM_ALTERACOES_PENDENTES)) return
    setTemPendencias(false)
    setSelecionadoId(proximo)
  }

  const carregar = useCallback(() => {
    setEstado({ tipo: 'carregando' })
    listarTreinadores()
      .then((resposta) => setEstado({ tipo: 'pronto', resposta }))
      .catch((motivo: unknown) => {
        const mensagem =
          motivo instanceof ApiError
            ? motivo.message
            : 'Nao foi possivel carregar os treinadores. Verifique a conexao.'
        setEstado({ tipo: 'erro', mensagem })
      })
  }, [])

  useEffect(() => {
    carregar()
  }, [carregar])

  if (estado.tipo === 'carregando') {
    return (
      <main className="tela-treinadores">
        <p>Carregando treinadores...</p>
      </main>
    )
  }

  if (estado.tipo === 'erro') {
    return (
      <main className="tela-treinadores">
        <p role="alert" className="mensagem-erro">
          {estado.mensagem}
        </p>
        <button type="button" onClick={carregar}>
          Tentar novamente
        </button>
      </main>
    )
  }

  const { resposta } = estado

  return (
    <main className="tela-treinadores">
      <header>
        <h1>Treinadores</h1>
        <Link to="/laboratorio">Voltar ao laboratorio</Link>
      </header>

      {resposta.items.length === 0 ? (
        <p className="aviso-vazio">
          Nenhum treinador no laboratorio ainda. Conclua o kit inicial para receber os tres
          primeiros.
        </p>
      ) : (
        <div className="treinadores-layout">
          <ul className="lista-treinadores-grade">
            {resposta.items.map((treinador) => (
              <li key={treinador.id}>
                <CartaoTreinador
                  treinador={treinador}
                  selecionado={treinador.id === selecionadoId}
                  onSelecionar={trocarSelecao}
                />
              </li>
            ))}
          </ul>

          {selecionadoId && (
            <MontarTime
              key={selecionadoId}
              treinadorId={selecionadoId}
              onSalvo={carregar}
              onFechar={() => trocarSelecao(selecionadoId)}
              onPendenciasMudaram={setTemPendencias}
            />
          )}
        </div>
      )}
    </main>
  )
}
