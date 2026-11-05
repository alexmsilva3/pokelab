import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { entrar } from '@/api/auth'
import { ApiError } from '@/api/client'
import { guardarSessao } from '@/store/auth'

export function Login() {
  const navigate = useNavigate()
  const [usuario, setUsuario] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  async function aoEnviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    setErro(null)
    setEnviando(true)

    try {
      const sessao = await entrar({ usuario, senha })
      guardarSessao(sessao)
      navigate('/laboratorio', { replace: true })
    } catch (motivo) {
      setErro(
        motivo instanceof ApiError
          ? motivo.message
          : 'Nao foi possivel entrar. Verifique a conexao e tente novamente.',
      )
    } finally {
      setEnviando(false)
    }
  }

  return (
    <main className="tela-auth">
      <h1>Entrar no laboratorio</h1>
      <form onSubmit={aoEnviar} noValidate>
        <label htmlFor="login-usuario">Usuario</label>
        <input
          id="login-usuario"
          name="usuario"
          autoComplete="username"
          value={usuario}
          onChange={(evento) => setUsuario(evento.target.value)}
          required
        />

        <label htmlFor="login-senha">Senha</label>
        <input
          id="login-senha"
          name="senha"
          type="password"
          autoComplete="current-password"
          value={senha}
          onChange={(evento) => setSenha(evento.target.value)}
          required
        />

        {erro && <p role="alert" className="mensagem-erro">{erro}</p>}

        <button type="submit" className="botao-primario" disabled={enviando}>
          {enviando ? 'Entrando...' : 'Entrar'}
        </button>
      </form>

      <p>
        Ainda nao tem laboratorio? <Link to="/registro">Registre-se</Link>
      </p>
    </main>
  )
}
