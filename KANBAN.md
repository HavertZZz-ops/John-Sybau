# Kanban - John Sybau

Espelha o board https://github.com/users/HavertZZz-ops/projects/8
As issues #N sao as do repositorio. Um item por commit entregue.

> O board do GitHub e um Projects **classico**, que nao tem API: nao da
> para mover card por automacao. O que muda sozinho sao as issues.

## Backlog

- [ ] #3  criacao dos sprites
- [ ] #5  sprite da mulher misteriosa
- [ ] #6  sprite do rei mago
- [ ] #7  sprite do stranger
- [ ] trilha sonora (nenhum pacote de audio baixado ainda)
- [ ] que as 4 areas de depois (o jogo tem 1)
- [ ] cenas da casa da Parish of the Undead (o pacote
      Top-Down_Retro_Interior esta pronto e sem uso)

## Em progreso

- [ ] combate por turnos no estilo Chrono Trigger, com o medidor de tempo
- [ ] abertura que ensina as mecanicas depois do caixao

## Feito

- [x] #1  criar repositorio
- [x] #2  criar ambiente pro pygame
- [x] #8  Kanban do projeto e .gitignore              (`2d98938`)
- [x] #9  Estrutura do projeto, requirements e settings (`fccd6d6`)
- [x] #10 Loop principal e sistema de cenas            (`a91f0ff`)
- [x] #11 Carregador de assets com placeholders e UI    (`14e831e`)
- [x] #12 Tela inicial com elenco placeholder e menu   (`3281755`)
- [x] #13 Documentacao: README e mapa de sprites       (`206f18b`)
- [x] #14  Sprites do heroi, dos inimigos e das armas  (`5d81b68`)
      166 quadros do heroi em 10 estados, 320 dos esqueletos
      (4 tipos, 4 direcoes, andar e ataque) e 8 folhas de arma.
      Duas folhas nao eram o que o nome dizia e foram medidas no alpha:
      a de ataque e o EFEITO DA ESPADA (32x32 e 32x48), e a do
      esqueleto e 16x32 com 2 linhas por direcao.
- [x] #15  Sistema de save com PostgreSQL via Django   (`a977226`)
      `src/saves.py` com dois lugares (arquivo sempre, Django quando
      responde), `server/` com o modelo Slot e API JSON, menu com
      Continuar e Novo jogo. 19/19 no teste do servidor e o caminho
      HTTP testado de ponta a ponta.
- [x] #16  Cenario: Catacumbas com saida pelo caixao    (`a977226`)
      7 salas geradas, camera com trava, colisao por eixo, sarcofago
      desenhado por codigo com a tampa que desliza, titulo de area.
- [x] #17  Menus minimalistas no estilo Dark Souls      (`2e1f28e`)
- [x] #18  Transicao de tela cheia corrompia a resolucao (`eb8cc88`)
      Em tela cheia nao ha moldura: a diferenca entre janela e superficie
      e o espaco da ESCALA, e ela entrava no filtro de resolucao.
      O primeiro `set_mode` ao sair do fullscreen tambem nao aplicava o
      tamanho novo.