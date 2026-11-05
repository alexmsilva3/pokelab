import { useEffect, useState } from 'react'
import { verificarSaude } from '@/api/client'

type Estado = 'carregando' | 'online' | 'offline'

export function Laboratorio() {
  const [estado, setEstado] = useState<Estado>('carregando')

  useEffect(() => {
    verificarSaude()
      .then(() => setEstado('online'))
      .catch(() => setEstado('offline'))
  }, [])

  return (
    <main style={{ padding: 'var(--espaco-5)', maxWidth: 960, margin: '0 auto' }}>
      <h1>PokeLab</h1>
      <p style={{ color: 'var(--cor-texto-suave)' }}>
        Fase 0 concluida. O laboratorio ainda nao abriu as portas.
      </p>
      <p data-testid="status-api">
        API: {estado === 'carregando' ? 'verificando...' : estado}
      </p>
    </main>
  )
}
