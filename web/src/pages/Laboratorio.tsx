import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { buscarPerfil } from '@/api/auth'
import { ApiError } from '@/api/client'
import type { PerfilCompleto } from '@/api/tipos'
import { limparSessao } from '@/store/auth'

type Estado =
  | { tipo: 'carregando' }
  | { tipo: 'erro'; mensagem: string }
  | { tipo: 'pronto'; perfil: PerfilCompleto }

export function Laboratorio() {
  const navigate = useNavigate()
  const [estado, setEstado] = useState<Estado>({ tipo: 'carregando' })

  const carregar = useCallback(() => {
    setEstado({ tipo: 'carregando' })
    buscarPerfil()
      .then((perfil) => setEstado({ tipo: 'pronto', perfil }))
      .catch((motivo: unknown) => {
        const mensagem =
          motivo instanceof ApiError
            ? motivo.message
            : 'Nao foi possivel carregar o laboratorio. Verifique a conexao.'
        setEstado({ tipo: 'erro', mensagem })
      })
  }, [])

  useEffect(() => {
    carregar()
  }, [carregar])

  function sair() {
    limparSessao()
    navigate('/login', { replace: true })
  }

  if (estado.tipo === 'carregando') {
    return (
      <main className="tela-laboratorio">
        <p>Carregando laboratorio...</p>
      </main>
    )
  }

  if (estado.tipo === 'erro') {
    return (
      <main className="tela-laboratorio">
        <p role="alert" className="mensagem-erro">{estado.mensagem}</p>
        <button type="button" onClick={carregar}>
          Tentar novamente
        </button>
      </main>
    )
  }

  const { professor, laboratorio, resumo } = estado.perfil
  const semTreinador = resumo.treinadores === 0

  return (
    <main className="tela-laboratorio">
      <header>
        <h1>{laboratorio.nome}</h1>
        <p>Professor {professor.nome_exibicao ?? professor.usuario}</p>
      </header>

      <dl className="resumo-laboratorio" aria-label="Resumo do laboratorio">
        <div>
          <dt>Nivel do laboratorio</dt>
          <dd>{laboratorio.nivel}</dd>
        </div>
        <div>
          <dt>Moedas</dt>
          <dd>{laboratorio.moedas}</dd>
        </div>
        <div>
          <dt>Pokemon</dt>
          <dd>{resumo.pokemon}</dd>
        </div>
        <div>
          <dt>Treinadores</dt>
          <dd>
            {resumo.treinadores} de {laboratorio.limite_treinadores}
          </dd>
        </div>
        <div>
          <dt>Locais desbloqueados</dt>
          <dd>{resumo.locais_desbloqueados}</dd>
        </div>
        <div>
          <dt>Pokedex</dt>
          <dd>
            {resumo.especies_capturadas} capturadas, {resumo.especies_vistas} vistas
          </dd>
        </div>
      </dl>

      {semTreinador && (
        <p className="aviso-vazio">
          Nenhum treinador no laboratorio. Recrute um para comecar a despachar expedicoes.
        </p>
      )}

      <button type="button" onClick={sair}>
        Sair
      </button>
    </main>
  )
}
