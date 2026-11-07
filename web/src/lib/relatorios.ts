/**
 * Vocabulario e apresentacao do relatorio de campo (spec 007). O conteudo de
 * cada evento — texto, minuto, numeros — vem pronto do servidor (Artigo II);
 * aqui so se traduz o tipo em rotulo e marcador visuais, igual a `lib/mapa.ts`
 * e `lib/expedicoes.ts` fazem para os outros vocabularios do jogo.
 *
 * `TipoDeEvento` e uniao fechada em `tipos.ts`, mas o valor que chega em
 * tempo de execucao e so mais um JSON do servidor: um tipo de evento novo que
 * o backend venha a mandar amanha nao pode render a tela em branco. Por isso
 * o rotulo e o marcador sao um `switch` com `default`, nunca um `Record`
 * indexado direto pelo tipo.
 */
import type { TipoDeEvento } from '@/api/tipos'

export function rotuloTipoEvento(tipo: TipoDeEvento | string): string {
  switch (tipo) {
    case 'PARTIDA':
      return 'Partida'
    case 'BATALHA':
      return 'Batalha'
    case 'CAPTURA':
      return 'Captura'
    case 'CAPTURA_FALHA':
      return 'Captura falhou'
    case 'BAGAGEM_CHEIA':
      return 'Bagagem cheia'
    case 'DESCOBERTA':
      return 'Descoberta'
    case 'ITEM':
      return 'Item encontrado'
    case 'CONTRATEMPO':
      return 'Contratempo'
    case 'SUBIU_NIVEL':
      return 'Subiu de nivel'
    case 'EVOLUCAO':
      return 'Evolucao'
    case 'RETORNO':
      return 'Retorno'
    default:
      return 'Evento'
  }
}

/**
 * Um unico caractere por tipo de evento, so decorativo (`aria-hidden`): o
 * rotulo em texto de `rotuloTipoEvento` e quem carrega o significado para
 * quem usa leitor de tela. Nenhum emoji — so pontuacao simples (Artigo X e a
 * natureza lista-e-botao da interface).
 */
export function marcadorTipoEvento(tipo: TipoDeEvento | string): string {
  switch (tipo) {
    case 'PARTIDA':
      return '>'
    case 'BATALHA':
      return '+'
    case 'CAPTURA':
      return '*'
    case 'CAPTURA_FALHA':
      return 'x'
    case 'BAGAGEM_CHEIA':
      return '!'
    case 'DESCOBERTA':
      return '?'
    case 'ITEM':
      return '$'
    case 'CONTRATEMPO':
      return '-'
    case 'SUBIU_NIVEL':
      return '^'
    case 'EVOLUCAO':
      return '~'
    case 'RETORNO':
      return '<'
    default:
      return '.'
  }
}

export function rotuloStatusRelatorio(
  status: 'CONCLUIDA_SUCESSO' | 'CONCLUIDA_FALHA',
): string {
  return status === 'CONCLUIDA_SUCESSO' ? 'Sucesso' : 'Falha'
}
