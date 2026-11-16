# Kikoia - Quadro Interativo

Quadro interativo para Windows e Android, que funciona de forma independente do teclado Kikoia.

## Recursos (`Resources/`)

Os recursos são descarregados pelo Quadro apenas quando o utilizador os pede.

- `Resources/index.json`: lista de jogos e ferramentas disponíveis. É o único ficheiro lido na abertura.
- `Resources/Games/<jogo>/game.json`: dados do jogo (nome, descrição, autores, copyright, licença, websites e fonte oficial de download).
- `Resources/Games/<jogo>/screenshots/`: imagem inicial (`thumb.png`) e restantes screenshots.
- `Resources/Images/`: imagens usadas pelas ferramentas.

Os jogos de terceiros **não são alojados aqui**: o `game.json` aponta para a fonte oficial, que é de onde o Quadro os descarrega.

## Créditos e licenças

| Recurso | Autor / copyright | Licença |
|---|---|---|
| GCompris | Timothée Giet and others | AGPL-3.0 |
| Solo (Simon Tatham's Portable Puzzle Collection) | Simon Tatham e outros contribuidores | MIT |

Os ficheiros de cada recurso indicam os seus próprios créditos.
