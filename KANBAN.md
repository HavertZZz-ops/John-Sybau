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

- [ ] mais areas: o jogo tem 1 de 4
- [ ] dinheiro e loot (o pacote de UI tem icones de moeda e inventario,
      ainda sem uso porque a paleta dele briga com o visual do jogo)
- [ ] PixelLab: servidor MCP a configurar, nenhuma arte gerada ainda

## Feito

- [x] #25  Tela de vitoria travada                      (`1d6b2a8`)
      Tres defeitos na mesma tela:
      - o texto dizia "qualquer tecla para voltar" e SO o Esc
        respondia. Qualquer tecla volta, e grava ao sair
      - a espada do golpe ficava congelada no heroi para sempre: o
        `update` retornava quando a luta acabava ANTES de desligar a
        animacao
      - o inimigo morto era um retangulo preto sobre o proprio sprite,
        que lia como um bloco solto no chao
- [x] #26  Inimigo principal com corpo de verdade       (`este commit`)
      O esqueleto do Skeletons Pack e uma arte de 6px de largura por 21
      de altura, medida no canal alpha. Mesmo normalizado para a altura
      do heroi, ele sai com 30px de largura contra 96 do jogador na
      escala 3x, e le como um palito. Nao da para consertar so por
      escala sem distorcer a arte.
      O `NPC_test` do pacote gfx e uma criatura de osso com bracos,
      pernas e sombra, em celulas de 16x32 numa grade de 4 por 4.
      Normalizado, sai com 56px de largura: quase o dobro. Virou o
      inimigo principal; o esqueleto continua como variante mais fraca.
      Medido: 323 fps a 1520x921 com o inimigo na tela.

- [x] #22  Performance: o jogo rodava a 22 fps        (`este commit`)
      Duas causas, ambas dentro do laco de desenho:
      - cada tile visivel era `transform.scale` a CADA quadro. Numa
        janela 1520x921 sao mais de 600 tiles, e 600 amplitudes por
        quadro. Agora o tileset e ampliado uma vez e fica em cache.
      - `_desenhar_esqueleto` chamava `load_foe` dentro do desenho:
        um glob na pasta, 8 PNGs abertos do disco e 8 escalas,
        sessenta vezes por segundo, so com o esqueleto na tela.
      Medido com `tools/medir_fps_dungeon.py` (superficie real):
      139 -> 332 fps sem esqueleto, e 324 fps com ele.
      `tools/medir_fps_dungeon.py` foi criado aqui: SDL dummy nao
      cobra blit, entao nenhum teste headless via lentidao real.
- [x] #24  Contraste do cenario                       (`este commit`)
      O veu da masmorra escurece a tela inteira e, com contraste
      baixo, o chao e a parede chegavam quase iguais: a tela virava um
      campo escuro sem leitura. A curva de luminancia passou a
      acentuar (ganho 2.05 em vez de 1.45) e o veu ficou mais leve.
      O desenho do tileset reaparece e o lugar fica legivel.
- [x] #23  Esqueleto com o dobro da altura do heroi    (`aab3f66`)
      A normalizacao espelhou a do heroi, mas a importacao JA
      multiplica por 2 antes de gravar. Normalizar para 32 produzia 64
      no disco e 192 na tela, o dobro do heroi. O alvo e dividido pelo
      `UPSCALE`: agora o arquivo tem 32 de altura, igual ao heroi, e na
      escala 3x os dois saem com 96.
      A arte do pacote e um esqueleto de 6px por 21, medido no alpha:
      ele continua estreito de proposito, mas do tamanho do jogador.

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
- [x] #19  Combate por turnos com medidor de tempo       (`af45657`)
      A regra e o ATB do Chrono Trigger: todo mundo tem uma barra que
      enche sozinha e age quando chega no fim. O jogador escolhe O QUE
      fazer, nao a ordem. Defender corta o dano pela metade e custa
      menos tempo do que o golpe forte.
- [x] #20  Alinhar o sprite do esqueleto                 (`af45657`)
      A folha nao segue a grade de 16px: o desenho fica num canto da
      celula e anda de lado entre quadros. Cada quadro agora e recortado
      pela propria arte e centralizado, apoiado pela base.
- [x] #21  Abertura que ensina as mecanicas              (`este commit`)
      7 aulas que entram jogando, somem quando o jogador faz a coisa e
      nunca bloqueiam o controle. Nao e painel nem manual.
      O esqueleto dorme na masmorra e so acorda depois de alguns
      passos, para a primeira luta nao ser uma emboscada.
- [x] #27  Heroi do pacote de mercado                (`df46c77`)
      Troca o heroi pelo espadachim lvl1 (cabelo castanho, tunica
      verde, espada e brilho vermelho no impacto). Medido, nao
      adivinhado: cada folha tem quadro de 64x64, 4 linhas = 4
      direcoes. Idle 12, walk 6, ataque 8, run 8, hit 5, death 7.
      Tres defeitos reais apareceram no caminho:
      - o `HERO_BASE` era um numero escrito a mao (32x32) que passava
        a mentir a cada troca de sprite e quebrava a escala sem aviso.
        Agora e medido do disco, nao declarado;
      - o carregador ordenava os quadros alfabeticamente, entao um
        idle de 12 quadros tocava na ordem 0,1,10,11,2,3...
      - `death` e `falling` sao estados SEM direcao: o jogo procura
        `hero_death_*.png`. Gravar `hero_sul_death_*` deixava a
        morte vazia em silencio, sem erro no log.
      Os 5 estados que o pacote nao tem sao derivados dos
      equivalentes, para o heroi nunca cair no desenho de reserva.
      `tools/preview_espadachim.py` foi criado aqui: mostra os
      estados lado a lado, para nao dar palpite no desenho.
- [x] #28  Coixao de pedra                              (este commit)
      O sarcofago era um retangulo com textura de tijolo. Agora e um
      tumulo: contorno octogonal com ombros largos na cabeca e nos pes,
      plinto mais escuro na base, buraco cavado na propria silhueta,
      cranio entalhado e cruz na tampa, e desgaste fixo.
      - o chanfro dos cantos passou a ser um valor proprio. Quando
        crescia junto com o recuo do interior, o buraco saia com o topo
        em ogiva e o caixao parecia uma capela;
      - o cranio era medido pelo LADO MAIOR da tampa e saia do tamanho
        de um rebite. Agora e pelo menor;
      - a pedra, o buraco, a tampa e as sombras sao montados uma vez
        por tamanho (`lru_cache`) e o desenho por quadro e so blit.
        Sem o cache o redesenho do poligono custou 100 fps da masmorra
        (318 -> 216) para produzir a mesma imagem. Com o cache: 329.
      `tools/preview_caixao.py` foi criado aqui: mostra a tampa em
      0/25/50/75/100% de abertura lado a lado.
- [x] #29  Cenarios com tileset Wang do PixelLab       (este commit)
      Os cenarios paravam no tileset do pacote, com indices fixos
      numa grade 12x13. Agora cada cenario e um tileset Wang 4x4
      gerado pelo PixelLab, e o tile de cada celula sai dos quatro
      VERTICES que ela toca. Adicionar cenario e uma entrada em
      `CENARIOS` (src/cenarios.py), sem tocar na cena.
      - `src/wang.py` monta a tabela de cantos a partir do METADATA do
        tileset, sem adivinhar a ordem dos bits do `wang_N`. Palpite na
        ordem dos bits poe a borda do lado errado;
      - o cache do desenho era chaveado pelo `id()` da imagem. O id de
        um objeto liberado volta a ser usado por outro, e o cache
        passava a devolver a peca errada sem nenhum aviso. Agora e
        chaveado pela chave de cantos. So isso levou a masmorra de
        214 para 419 fps;
      - a paleta e ajustada por tile, e nao mais na tela inteira. O
        filtro antigo foi afinado para o tileset do pacote e esmagava o
        novo num campo quase preto. Como a tabela Wang sabe quais
        cantos sao parede, parede escurece e chao clareia sem adivinhar
        pelo desenho;
      - o primeiro tileset saiu com o CHAO em laje, que sob o veu da
        masmorra lia como parede: o jogador via um corredor de tijolo
        em todo lugar. O prompt passou a pedir terra e cascalho, sem
        padrao de alvenaria.
      Dois cenarios: Catacumbas (terra e tijolo) e Cemiterio (terra
      morta e muro com vinha). `tools/test_wang.py` cobre a escolha do
      tile, incluindo o caso que pega permutao de cantos, e roda dentro
      do `test_smoke.py`. `tools/preview_cenario.py` mostra a sala
      autotilada de cada cenario.
- [x] #30  A masmorra como campanha de 5 salas       (este commit)
      A masmorra deixou de ser um mapa com uma luta. Sao cinco salas em
      ordem, e cada uma ensina UMA mecanica de combate:
        1 Ataacar   2 Defender   3 Habilidade   4 Usar item   5 Fugir
      O esqueleto nasce na sala em que o jogador esta, e nao no meio do
      mapa. A sala 4 e a excecao: o esqueleto dela so aparece quando o
      jogador pega a pocao, para a aula do item comecar com o item na
      mao.
      - o numero de salas e uma REGRA, e o gerador aceitava o que
        coubesse. A semente 23 dava 4 salas, a saida ia para a 4 e a
        mecanica de fuga nunca aparecia. As salas ocupam slots de uma
        grade com jitter agora: 14 sementes, todas com saida na 5;
      - a espera de passos do esqueleto valia so para as salas que nao
        eram a primeira. Invertida, a sala 1 punha o esqueleto no ar no
        instante em que a abertura acabava;
      - o numero da sala vem da POSICAO, e nao de um contador. Andar
        para tras e voltar nao pode fazer a dica piscar.
- [x] #31  Estrada, aldeia e os moradores             (este commit)
      A fuga da masmorra tinha que levar a algum lugar. `road_scene.py`
      e o trecho entre a masmorra e a aldeia; `city_scene.py` e a
      aldeia, com quatro moradores que tem nome e uma frase cada. Sem
      loja e sem cura: o lugar existe para dar para onde ir.
      O Esc com alguem perto fecha a conversa antes de sair da cidade.
- [x] #32  A campanha sobrevive ao save               (este commit)
      O save gravava posicao e tempo, e o progresso da campanha vivia
      so na memoria. A sala, a pocao, o chefe recambiado e o mundo
      aberto voltavam ao zero a cada F5, sem reclamar.
      Agora o progresso vai em `Save.extra`. Estrada e aldeia nao tem
      posicao que faca sentido no mapa da masmorra e nao descrevem
      cena nenhuma, entao o gerenciador grava o progresso sozinho
      quando a cena ativa nao sabe se descrever.

## Pacotes de arte externos importados

- [x] #33  A arte de UI entra no inventario, loja, equipamento e combate
      O pacote Craftpix entra em `assets/ui`, recolorido para a paleta
      de pedra e ouro do jogo. Tres bugs de verdade apareceram:
        - o R estava com o teste ANINHADO dentro do Q nas tres cenas, e
          o submenu de equipamento nunca abria em lugar nenhum;
        - `_desenhar_equipamento` estava definido e nunca chamado;
        - o `Action_panel` nao tem painel nenhum: e folha solta sem a
          grade que o detector procura. Foi fatiado na mao.
      No combate o que cabe no slot e o ICONE, porque "HABILIDADE" com
      13px passa de 70px e invadia o slot vizinho. O nome da acao
      escolhida fica na faixa de cima.
      A posicao dos slots da loja foi MEDIDA com `tools/medir_loja.py`,
      nao estimada: a folha tem a grade dos slots em 10% da altura, e
      nos 24% que serve ao inventario eles caem em cima do titulo.
- [x] #34  O Q fecha o inventario, e o primeiro esqueleto e fraco
      O Q chamava `_fechar_outros_menus()` e depois `not
      inventario_aberto`: como o primeiro zera a flag, o not a
      reabria, e o painel nunca saia de tela. A dica "q ou esc fecha"
      embaixo dele era mentira. Agora `_fechar_outros_menus` aceita
      `mantem_inventario`, que e o que o Q usa.
      E o campo `fracos` do progresso, que existia desde o comeco e
      ninguem lia: a sala 1 montava o mesmo esqueleto das outras, so
      que com a placa de "aqui voce aprende". Agora vida 12, forca 3,
      defesa 0 e barra lenta.
- [x] #35  A taverna e um lugar de verdade             (este commit)
      A taverna era um telhado na aldeia e um botao de pernoitar na
      porta. Agora o E na porta entra no salao: balcao, adega, mesas,
      estantes, relogio, lareira, poltronas, tapetes e o Tao Anchieta
      atras do balcao. A planta e um mapa de texto de 23x11, e as
      pecas sao recortadas por `tools/fatiar_interior.py` na grade de
      16px em que o pacote foi desenhado.
      Falar com o Tao na porta da rua e o que faz dormir; e ai que se
      paga e se cura, igual antes.
      Quatro coisas quebraram nesta cena e valem registro:
        - a planta saiu com linhas de 21, 22 e 23 colunas, e o desenho
          estourava em `PLANTA[y + 1][x]`. O script que escreve a
          planta agora recusa gravar uma linha torta;
        - a escala vinha da LARGURA da peca, e o balcao de 112px ficava
          com um terco do tamanho da area que ocupa. Agora vem da grade
          de arte;
        - uma peca grande era desenhada uma vez por celula, e o balcao
          de sete celulas aparecia sete vezes enfileirado;
        - o teste de "esta e o canto da peca?" usava a altura anotada a
          mao, e o tapete (altura 0, e chao) virava cinco tapetes
          empilhados.
- [x] #36  O E na estrada nao quebrava mais           (este commit)
      `road_scene` usava `self._avisar_tempo`, atributo que nao existe
      na cena: o nome do contador e `avisar_tempo`. O E na estrada
      quebrava com AttributeError, e como a fuga da masmorra passa por
      ali, o caminho para a aldeia estava cortado. Achado pelo fumaco
      longo depois que a taverna entrou na lista de cenas.
