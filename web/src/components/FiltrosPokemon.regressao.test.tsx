import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ValoresFiltroPokemon } from '@/components/FiltrosPokemon'
import { FiltrosPokemon } from '@/components/FiltrosPokemon'

/**
 * O atributo min do input numerico e so dica visual: o navegador deixa digitar
 * 0, o servidor recusa com 422, e o acervo inteiro sumia atras de uma mensagem
 * de erro por causa de uma tecla.
 */
describe('FiltrosPokemon — regressao da revisao da Fase 3', () => {
  function renderFiltros(valores: ValoresFiltroPokemon = {}, onMudar = vi.fn()) {
    render(<FiltrosPokemon valores={valores} onMudar={onMudar} />)
    return onMudar
  }

  it('nivel zero digitado e elevado ao minimo valido', () => {
    const onMudar = renderFiltros()
    fireEvent.change(screen.getByLabelText(/nivel minimo/i), { target: { value: '0' } })
    expect(onMudar).toHaveBeenCalledWith(expect.objectContaining({ nivelMin: 1 }))
  })

  it('nivel acima de 100 e reduzido ao maximo valido', () => {
    const onMudar = renderFiltros()
    fireEvent.change(screen.getByLabelText(/nivel maximo/i), { target: { value: '999' } })
    expect(onMudar).toHaveBeenCalledWith(expect.objectContaining({ nivelMax: 100 }))
  })

  it('campo esvaziado remove o filtro em vez de mandar zero', () => {
    // Parte de um filtro ativo: esvaziar um campo ja vazio nao dispara change.
    const onMudar = renderFiltros({ nivelMin: 25 })
    fireEvent.change(screen.getByLabelText(/nivel minimo/i), { target: { value: '' } })
    expect(onMudar).toHaveBeenCalledWith(expect.objectContaining({ nivelMin: undefined }))
  })

  it('nivel valido passa intacto', () => {
    const onMudar = renderFiltros()
    fireEvent.change(screen.getByLabelText(/nivel minimo/i), { target: { value: '25' } })
    expect(onMudar).toHaveBeenCalledWith(expect.objectContaining({ nivelMin: 25 }))
  })
})
