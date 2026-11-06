import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { buscarPokedex } from '@/api/pokedex'
import type { RespostaPokedex } from '@/api/tipos'
import { CartaoPokedex } from '@/components/CartaoPokedex'

type Estado =
  | { tipo: 'carregando' }
  | { tipo: 'erro'; mensagem: string }
  | { tipo: 'pronto'; resposta: RespostaPokedex }

export function Pokedex() {
  const [estado, setEstado] = useState<Estado>({ tipo: 'carregando' })

  const carregar = useCallback(() => {
    setEstado({ tipo: 'carregando' })
    buscarPokedex()
      .then((resposta) => setEstado({ tipo: 'pronto', resposta }))
      .catch((motivo: unknown) => {
        const mensagem =
          motivo instanceof ApiError
            ? motivo.message
            : 'Nao foi possivel carregar a Pokedex. Verifique a conexao.'
        setEstado({ tipo: 'erro', mensagem })
      })
  }, [])

  useEffect(() => {
    carregar()
  }, [carregar])

  if (estado.tipo === 'carregando') {
    return (
      <main className="tela-pokedex">
        <p>Carregando Pokedex...</p>
      </main>
    )
  }

  if (estado.tipo === 'erro') {
    return (
      <main className="tela-pokedex">
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

  if (resposta.items.length === 0) {
    return (
      <main className="tela-pokedex">
        <p className="aviso-vazio">
          A Pokedex ainda nao tem entradas. Volte ao laboratorio para comecar a explorar.
        </p>
      </main>
    )
  }

  return (
    <main className="tela-pokedex">
      <header>
        <h1>Pokedex</h1>
        <Link to="/laboratorio">Voltar ao laboratorio</Link>
      </header>

      <p className="pokedex-resumo">
        {resposta.capturadas} capturadas e {resposta.vistas} vistas de 151
      </p>

      <ul className="grade-pokedex">
        {resposta.items.map((entrada) => (
          <CartaoPokedex key={entrada.numero} entrada={entrada} />
        ))}
      </ul>
    </main>
  )
}
