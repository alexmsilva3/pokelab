/**
 * Respostas de exemplo da API, TIPADAS.
 *
 * Existe porque um mock escrito a mao num teste inventou um campo que o
 * servidor nunca mandou (`especies_pokedex`), o `tsc` nao reclamou — o objeto
 * literal ia para dentro de `json: async () => (...)`, que e `Promise<any>` —
 * e a tela renderizou vazio com a suite verde.
 *
 * Todo mock de resposta passa por aqui. Se o contrato do servidor mudar e os
 * tipos de `tipos.ts` forem atualizados, estes helpers quebram na compilacao
 * em vez de deixarem o teste mentir.
 */

import type { PerfilCompleto, Professor, ResumoLaboratorio, Sessao } from '@/api/tipos'

export function professorExemplo(sobrescritas: Partial<Professor> = {}): Professor {
  return { id: '1', usuario: 'ash', nome_exibicao: 'Ash', ...sobrescritas }
}

export function laboratorioExemplo(
  sobrescritas: Partial<Sessao['laboratorio']> = {},
): Sessao['laboratorio'] {
  return {
    id: '10',
    nome: 'Lab Pallet',
    nivel: 1,
    experiencia: 0,
    moedas: 0,
    limite_treinadores: 3,
    ...sobrescritas,
  }
}

export function resumoExemplo(
  sobrescritas: Partial<ResumoLaboratorio> = {},
): ResumoLaboratorio {
  return {
    pokemon: 3,
    treinadores: 1,
    locais_desbloqueados: 1,
    especies_vistas: 3,
    especies_capturadas: 3,
    ...sobrescritas,
  }
}

export function sessaoExemplo(sobrescritas: Partial<Sessao> = {}): Sessao {
  return {
    token: 'token-valido',
    professor: professorExemplo(),
    laboratorio: laboratorioExemplo(),
    ...sobrescritas,
  }
}

export function perfilExemplo(sobrescritas: Partial<PerfilCompleto> = {}): PerfilCompleto {
  return {
    professor: professorExemplo(),
    laboratorio: laboratorioExemplo(),
    resumo: resumoExemplo(),
    ...sobrescritas,
  }
}
