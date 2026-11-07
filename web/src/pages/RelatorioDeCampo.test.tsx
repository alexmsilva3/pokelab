import { render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { expedicaoLerExemplo, relatorioDeCampoExemplo } from '@/api/fixtures'
import type { ExpedicaoLer } from '@/api/tipos'
import { RelatorioDeCampo } from '@/pages/RelatorioDeCampo'

function respostaJson(corpo: unknown, status = 200) {
  return { ok: status < 400, status, json: async () => corpo }
}

function renderRelatorio(
  id = 'expedicao-1',
  opcoes: { estadoDeNavegacao?: { expedicao: ExpedicaoLer } } = {},
) {
  return render(
    <MemoryRouter
      initialEntries={[
        { pathname: `/expedicoes/${id}/relatorio`, state: opcoes.estadoDeNavegacao },
      ]}
    >
      <Routes>
        <Route path="/expedicoes/:id/relatorio" element={<RelatorioDeCampo />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('RelatorioDeCampo', () => {
  it('mostra o resultado, as capturas, as tres experiencias, os itens e a linha do tempo', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        respostaJson(
          expedicaoLerExemplo({
            treinador_nome: 'Ash',
            local_destino_nome: 'Route 1',
            status: 'CONCLUIDA_SUCESSO',
            estado_observado: 'CONCLUIDA_SUCESSO',
            relatorio: relatorioDeCampoExemplo({ local_desbloqueado: true }),
          }),
        ),
      ),
    )

    renderRelatorio()

    expect(await screen.findByText(/Sucesso\./)).toBeInTheDocument()
    expect(screen.getByText(/Ash voltou de Route 1/)).toBeInTheDocument()
    expect(screen.getByText(/local foi desbloqueado/)).toBeInTheDocument()

    expect(screen.getByText('Caterpie')).toBeInTheDocument()
    expect(screen.getByText('Nv. 5')).toBeInTheDocument()

    expect(screen.getByRole('region', { name: 'Experiencia do time' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Experiencia do treinador' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Experiencia do laboratorio' })).toBeInTheDocument()

    expect(screen.getByRole('region', { name: 'Itens' })).toBeInTheDocument()
    expect(screen.getByText('Poke Ball')).toBeInTheDocument()
    expect(screen.getByText('Potion')).toBeInTheDocument()

    const secaoLinhaDoTempo = screen.getByRole('region', { name: 'Linha do tempo' })
    const timeline = within(secaoLinhaDoTempo).getByRole('list')
    expect(timeline.tagName).toBe('OL')
    expect(within(secaoLinhaDoTempo).getAllByRole('listitem')).toHaveLength(3)
  })

  it('relatorio nulo nao quebra a tela', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        respostaJson(
          expedicaoLerExemplo({
            status: 'ABORTADA',
            estado_observado: 'ABORTADA',
            relatorio: null,
          }),
        ),
      ),
    )

    renderRelatorio()

    expect(
      await screen.findByText('Esta expedicao foi abortada antes de gerar relatorio.'),
    ).toBeInTheDocument()
  })

  it('chegando com a expedicao do claim, mostra o relatorio sem refazer o GET', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    const expedicao = expedicaoLerExemplo({
      treinador_nome: 'Ash',
      local_destino_nome: 'Route 1',
      status: 'CONCLUIDA_SUCESSO',
      estado_observado: 'CONCLUIDA_SUCESSO',
      relatorio: relatorioDeCampoExemplo({ local_desbloqueado: true }),
    })

    renderRelatorio('expedicao-1', { estadoDeNavegacao: { expedicao } })

    expect(await screen.findByText(/Sucesso\./)).toBeInTheDocument()
    expect(screen.getByText(/Ash voltou de Route 1/)).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('exibe mensagem de erro do servidor e permite tentar novamente', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          respostaJson(
            { erro: { codigo: 'ERRO_INTERNO', mensagem: 'Nao foi possivel carregar o relatorio.' } },
            500,
          ),
        ),
    )

    renderRelatorio()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Nao foi possivel carregar o relatorio.',
    )
    expect(screen.getByRole('button', { name: /tentar novamente/i })).toBeInTheDocument()
  })
})
