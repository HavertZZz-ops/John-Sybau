# Onde os sprites do jogo moram

O jogo nao traz nenhum sprite pronto. Tudo aqui dentro foi feito para
receber arte **dela**.

A pasta fica vazia de proposito: um jogo com arte emprestada e um jogo
com arte propria tem problemas diferentes, e so o segundo e o seu.

---

## Como o jogo procura um sprite

Por nome logico, com **barra** (nunca barra invertida — no Windows as
duas funcionam, mas so a barra funciona em qualquer sistema):

```python
import arte

imagem = arte.carregar_sprite("heroi/idl_sul.png", escala=3)
tela.blit(imagem, (x, y))
```

O caminho na maquina e `game/assets/sprites/heroi/idl_sul.png`.

---

## A regra da transparencia

Esta e a unica regra que o jogo **nao** adivinha direito, entao vale
entender.

Existe duas formas de dizer "aqui dentro nao tem desenho", e usar a
errada estraga o sprite:

| Jeito | Como e | Quem usa |
|---|---|---|
| Cor-chave | fundo de uma cor solida (o jogo usa **magenta** `#FF00FF`) | sprite sheets antigos |
| Canal alpha | o proprio PNG tem transparencia | Aseprite, Krita, Photoshop |

O jogo **descobre sozinho** qual dos dois e, olhando o primeiro pixel da
imagem. Funciona na maioria dos casos. Se o seu sprite tem um fundo de
verdade no canto (uma cena, um retrato), e o jogo concluir errado, force
o modo:

```python
arte.carregar_sprite("heroi/retrato.png", escala=2, usar_alpha=True)
```

E se quiser o oposto, `usar_alpha=False` para apagar o magenta.

---

## Tamanho e escala

O jogo roda em **800x600** e o tile tem **32px**. O tamanho de arte que
faz sentido nesse tamanho:

- **heroi**: 16x16 ou 24x24 de arte, com `escala=2` vira 32x32 ou 48x48
- **inimigos**: mesmo tamanho do heroi, para a briga na tela ficar justa
- **cenario**: 32x32, exatamente um tile
- **tiles**: 16x16 se voce desenhar tiles, 32x32 se forem blocos inteiros

`escala` multiplica. Com `escala=3` um sprite de 16px vira 48px.

A escala e feita **sem filtro suave** (`scale`, nao `smoothscale`), para o
quadriculado do pixel art continuar quadrado. Se voce ampliar com
interpolacao, o sprite chega borroso.

---

## Nomes sugeridos

O nome do arquivo e o que o jogo chama. Nao ha convencao obrigatoria, mas
uma nomenclatura consistente evita o tipo de bug em que o turno de frente
do heroi usa o desenho de costas.

```
sprites/heroi/
    idl_sul.png      idl_norte.png     idl_leste.png     idl_oeste.png
    anda_sul.png     anda_norte.png    anda_leste.png    anda_oeste.png
    corr_sul.png     corr_norte.png    corr_leste.png    corr_oeste.png

sprites/inimigos/
    esqueleto_anda_sul.png    esqueleto_ataca_sul.png
    lobisomem_anda_sul.png     lobisomem_ataca_sul.png

sprites/cenario/
    bau_fechado.png    bau_aberto.png    tocha_acessa.png

tiles/
    chao_terra.png    parede_pedra.png
```

`sul` e a frente (o personagem olhando para a camera), `norte` e as
costas. `anda` e o caminhar, `ataca` e o golpe, `corr` e a corrida.

---

## Animacao com varios quadros

Varias imagens em uma so, lado a lado. O jogo corta:

```python
frames = arte.carregar_sheet("heroi/anda_sul.png", quadros=6, colunas=6, escala=2)
```

`quadros` e quantas fatias tem, `colunas` e quantas cabem numa linha. Se
a imagem for menor do que o grid diz, os quadros que faltam repetem o
ultimo — o jogo nao quebra, ele repete.

---

## Se um sprite nao aparecer

Vai aparecer um **retangulo magenta** com o nome do arquivo escrito
dentro. Isso e proposital: e mais util do que um espaco vazio, porque
diz exatamente o que falta.

Para ver no console o que o jogo tentou carregar:

```python
arte.definir_depuração(True)
...
print(arte.erros_de_carregamento())
```

---

## Sons

`assets/sfx/` e para efeitos. Carregamento de som ainda nao foi escrito;
quando for, o caminho vai ser `assets/sfx/nome.ogg`.