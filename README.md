# John-Sybau

Prototipo de jogo 2D em Python + Pygame. feito em pygame.
https://www.spritefusion.com/pixel-art-generator/editor
ae72a5ce-0d00-41bc-a80d-fea4658e0b1e

## Como rodar

```bash
pip install -r requirements.txt
python run.py
```

## Como testar sem abrir janela

```bash
python test_smoke.py
```

## Controles

- setas ou W/S: navegar no menu
- enter ou espaco: confirmar
- esc: sair

## Sprites

O jogo roda sem nenhum arquivo de arte. Para cada personagem o jogo
procura um PNG em `assets/sprites/` e, enquanto o arquivo nao existir,
desenha um retangulo no lugar.

| arquivo                      | personagem        |
| ---------------------------- | ----------------- |
| `protagonista.png`           | Protagonista      |
| `estranho.png`               | Estranho          |
| `mulher_misteriosa.png`      | Mulher misteriosa |
| `rei_mago.png`               | Rei mago          |

Ao adicionar o arquivo, o cartao correspondente passa a mostrar
"sprite ok" na tela inicial. O carregamento escala a imagem para
78x110 automaticamente.

## Estrutura

```
run.py              ponto de entrada
src/settings.py     resolucao, cores, caminhos
src/scene.py        classe base das cenas
src/scene_manager.py trocas de cena
src/title_screen.py tela inicial
src/assets.py       sprites + placeholders
src/ui.py           texto e paineis
test_smoke.py       teste headless
```

Veja o [KANBAN.md](KANBAN.md) para o que falta.
