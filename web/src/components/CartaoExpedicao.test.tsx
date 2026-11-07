import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { expedicaoLerExemplo, pokemonResumoExemplo, respostaClaimExpedicaoExemplo } from '@/api/fixtures'
import { CartaoExpedicao } from '@/components/CartaoExpedicao'
import { RelatorioDeCampo } from '@/pages/RelatorioDeCampo'

function respostaJson(corpo: unknown, status = 200) {
  return { ok: status < 400, status, json: async () => corpo }
}

function renderCartao(
  sobrescritas: Parameters<typeof expedicaoLerExemplo>[0] = {},
  extras: { onAtualizar?: () => void; onAbortar?: () => void; onChegarAZero?: () => void } = {},
) {
  const expedicao = expedicaoLerExemplo(sobrescritas)
  const onAbortar = extras.onAbortar ?? vi.fn()
  const onChegarAZero = extras.onChegarAZero ?? vi.fn()
  const onAtualizar = extras.onAtualizar ?? vi.fn()

  render(
    <MemoryRouter initialEntries={['/expedicoes']}>
      <Routes>
        <Route
          path="/expedicoes"
          element={
            <CartaoExpedicao
              expedicao={expedicao}
              abortando={false}
              onAbortar={onAbortar}
              onChegarAZero={onChegarAZero}
              onAtualizar={onAtualizar}
            />
          }
        />
        <Route
          path="/expedicoes/:id/relatorio"
          element={<p>Tela do relatorio de {expedicao.treinador_nome}</p>}
        />
      </Routes>
    </MemoryRouter>,
  )

  return { expedicao, onAbortar, onChegarAZero, onAtualizar }
}

describe('CartaoExpedicao', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('aguardando relatorio mostra "Receber relatorio" como acao primaria', () => {
    renderCartao({ estado_observado: 'AGUARDANDO_RELATORIO' })

    expect(screen.getByRole('button', { name: 'Receber relatorio' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Ver relatorio' })).not.toBeInTheDocument()
  })

  it('estado terminal mostra "Ver relatorio" em vez de "Receber relatorio"', () => {
    renderCartao({ estado_observado: 'CONCLUIDA_SUCESSO' })

    expect(screen.getByRole('button', { name: 'Ver relatorio' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Receber relatorio' })).not.toBeInTheDocument()
  })

  it('clicar em "Receber relatorio" chama o claim uma unica vez mesmo com dois cliques, e navega para o relatorio', async () => {
    const fetchMock = vi.fn().mockResolvedValue(respostaJson(respostaClaimExpedicaoExemplo()))
    vi.stubGlobal('fetch', fetchMock)

    renderCartao({
      id: 'expedicao-1',
      treinador_nome: 'Ash',
      estado_observado: 'AGUARDANDO_RELATORIO',
    })

    const botao = screen.getByRole('button', { name: 'Receber relatorio' })
    fireEvent.click(botao)
    fireEvent.click(botao)

    expect(await screen.findByText('Tela do relatorio de Ash')).toBeInTheDocument()

    const chamadasDeClaim = fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')
    expect(chamadasDeClaim).toHaveLength(1)
  })

  it('ao receber o relatorio, a tela de destino usa o corpo do claim sem refazer o GET', async () => {
    const resposta = respostaClaimExpedicaoExemplo()
    const fetchMock = vi.fn().mockResolvedValue(respostaJson(resposta))
    vi.stubGlobal('fetch', fetchMock)

    const expedicao = expedicaoLerExemplo({ id: 'expedicao-1', estado_observado: 'AGUARDANDO_RELATORIO' })

    render(
      <MemoryRouter initialEntries={['/expedicoes']}>
        <Routes>
          <Route
            path="/expedicoes"
            element={
              <CartaoExpedicao
                expedicao={expedicao}
                abortando={false}
                onAbortar={vi.fn()}
                onChegarAZero={vi.fn()}
                onAtualizar={vi.fn()}
              />
            }
          />
          <Route path="/expedicoes/:id/relatorio" element={<RelatorioDeCampo />} />
        </Routes>
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Receber relatorio' }))

    expect(await screen.findByText(/Sucesso\./)).toBeInTheDocument()

    // Uma unica chamada de rede no fluxo inteiro: o POST do claim. Nenhum
    // GET /expeditions/{id} e refeito so para reler o que o claim ja trouxe.
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][1]?.method).toBe('POST')
  })

  it('recusa EXPEDICAO_EM_CURSO mostra a mensagem do servidor e reconsulta a lista', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        respostaJson(
          {
            erro: {
              codigo: 'EXPEDICAO_EM_CURSO',
              mensagem: 'O prazo desta expedicao ainda nao venceu.',
            },
          },
          409,
        ),
      ),
    )

    const { onAtualizar } = renderCartao({ estado_observado: 'AGUARDANDO_RELATORIO' })

    fireEvent.click(screen.getByRole('button', { name: 'Receber relatorio' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'O prazo desta expedicao ainda nao venceu.',
    )
    expect(onAtualizar).toHaveBeenCalled()
  })

  it('clicar em "Ver relatorio" navega sem chamar a API', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    renderCartao({ id: 'expedicao-9', treinador_nome: 'Misty', estado_observado: 'CONCLUIDA_FALHA' })

    fireEvent.click(screen.getByRole('button', { name: 'Ver relatorio' }))

    expect(screen.getByText('Tela do relatorio de Misty')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

describe('botao de abortar', () => {
  it('aparece enquanto a expedicao esta em curso', () => {
    renderCartao({ estado_observado: 'EM_CURSO', segundos_restantes: 120 })

    expect(screen.getByRole('button', { name: 'Abortar' })).toBeInTheDocument()
  })

  it('some quando o prazo vence, porque o servidor recusa abortar fora de EM_CURSO', () => {
    // Regressao: o cartao escondia o botao so nos estados terminais, e
    // AGUARDANDO_RELATORIO nao esta entre eles — vencido o prazo, "Abortar"
    // seguia habilitado e o clique levava 409 do servidor.
    renderCartao({ estado_observado: 'AGUARDANDO_RELATORIO', segundos_restantes: 0 })

    expect(screen.queryByRole('button', { name: 'Abortar' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Receber relatorio' })).toBeInTheDocument()
  })

  it.each(['CONCLUIDA_SUCESSO', 'CONCLUIDA_FALHA', 'ABORTADA'] as const)(
    'some no estado terminal %s',
    (estado) => {
      renderCartao({ estado_observado: estado, segundos_restantes: null })

      expect(screen.queryByRole('button', { name: 'Abortar' })).not.toBeInTheDocument()
    },
  )
})

describe('treinador em campo', () => {
  it('mostra o retrato e o time de quem esta fora', () => {
    // O painel existe para o professor lembrar QUEM mandou e com o que, sem
    // abrir a tela de treinadores.
    renderCartao({
      treinador_nome: 'Pat',
      treinador_time: [
        pokemonResumoExemplo({ id: 'p1', especie_nome: 'Bulbasaur', nivel: 7 }),
        pokemonResumoExemplo({ id: 'p2', especie_nome: 'Pidgey', nivel: 4 }),
      ],
    })

    expect(screen.getByRole('list', { name: 'Time de Pat' })).toBeInTheDocument()
    expect(screen.getByText(/Bulbasaur Nv. 7/)).toBeInTheDocument()
    expect(screen.getByText(/Pidgey Nv. 4/)).toBeInTheDocument()
  })

  it('o retrato nao vira ruido para leitor de tela', () => {
    // O nome ja esta no <h3> ao lado; o retrato repetiria a mesma informacao,
    // entao ele fica escondido da arvore de acessibilidade. `queryByRole` so
    // enxerga o que esta exposto — se o retrato vazasse, este teste pegaria.
    renderCartao({ treinador_nome: 'Pat' })

    expect(screen.queryByRole('img', { name: 'Retrato de Pat' })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Pat' })).toBeInTheDocument()
  })

  it('treinador sem time nao desenha lista vazia', () => {
    renderCartao({ treinador_nome: 'Pat', treinador_time: [] })

    expect(screen.queryByRole('list', { name: 'Time de Pat' })).not.toBeInTheDocument()
  })
})
