import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { registrar } from '@/api/auth'
import { ApiError } from '@/api/client'
import { guardarSessao } from '@/store/auth'

// Validacao de bolso para feedback imediato. O servidor e a autoridade
// (Artigo II): esta checagem nunca substitui a dele, so evita uma viagem
// de rede para um erro obvio.
const TAMANHO_MINIMO_SENHA = 8

export function Registro() {
  const navigate = useNavigate()
  const [usuario, setUsuario] = useState('')
  const [senha, setSenha] = useState('')
  const [confirmarSenha, setConfirmarSenha] = useState('')
  const [nomeLaboratorio, setNomeLaboratorio] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  async function aoEnviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    setErro(null)

    if (senha.length < TAMANHO_MINIMO_SENHA) {
      setErro(`A senha deve ter no minimo ${TAMANHO_MINIMO_SENHA} caracteres.`)
      return
    }

    if (senha !== confirmarSenha) {
      setErro('As senhas nao coincidem.')
      return
    }

    setEnviando(true)
    try {
      const sessao = await registrar({
        usuario,
        senha,
        ...(nomeLaboratorio.trim() ? { nome_laboratorio: nomeLaboratorio.trim() } : {}),
      })
      guardarSessao(sessao)
      navigate('/laboratorio', { replace: true })
    } catch (motivo) {
      setErro(
        motivo instanceof ApiError
          ? motivo.message
          : 'Nao foi possivel criar a conta. Verifique a conexao e tente novamente.',
      )
    } finally {
      setEnviando(false)
    }
  }

  return (
    <main className="tela-auth">
      <h1>Criar laboratorio</h1>
      <form onSubmit={aoEnviar} noValidate>
        <label htmlFor="registro-usuario">Usuario</label>
        <input
          id="registro-usuario"
          name="usuario"
          autoComplete="username"
          value={usuario}
          onChange={(evento) => setUsuario(evento.target.value)}
          required
        />

        <label htmlFor="registro-senha">Senha</label>
        <input
          id="registro-senha"
          name="senha"
          type="password"
          autoComplete="new-password"
          value={senha}
          onChange={(evento) => setSenha(evento.target.value)}
          required
          minLength={TAMANHO_MINIMO_SENHA}
        />

        <label htmlFor="registro-confirmar-senha">Confirmar senha</label>
        <input
          id="registro-confirmar-senha"
          name="confirmarSenha"
          type="password"
          autoComplete="new-password"
          value={confirmarSenha}
          onChange={(evento) => setConfirmarSenha(evento.target.value)}
          required
        />

        <label htmlFor="registro-nome-laboratorio">Nome do laboratorio (opcional)</label>
        <input
          id="registro-nome-laboratorio"
          name="nomeLaboratorio"
          value={nomeLaboratorio}
          onChange={(evento) => setNomeLaboratorio(evento.target.value)}
        />

        {erro && <p role="alert" className="mensagem-erro">{erro}</p>}

        <button type="submit" className="botao-primario" disabled={enviando}>
          {enviando ? 'Criando...' : 'Criar conta'}
        </button>
      </form>

      <p>
        Ja tem conta? <Link to="/login">Entrar</Link>
      </p>
    </main>
  )
}
