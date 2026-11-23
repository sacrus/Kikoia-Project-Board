# Créditos e licenças (Quadro Interativo)

O Quadro usa componentes de terceiros. Cada um mantém a sua própria licença.

**Licença do código do Quadro:** *a definir pelo autor antes da publicação* (ver o ficheiro `CREDITOS.md` do projeto principal, secção «Pontos em aberto»).

## Componentes usados

| Componente | Para que serve | Licença | Como é usado |
|---|---|---|---|
| Python (interpretador) | Corre o programa; vai dentro do executável Windows | PSF-2.0 | Incluído no executável |
| PySide6 e shiboken6 (Qt for Python) | Interface gráfica | LGPL-3.0 (também GPL-2.0 ou GPL-3.0; usamos LGPL-3.0) | Incluído no executável |
| libjxl (`cjxl` e `djxl`, v0.13.0) | Codificação e descodificação de imagens JPEG XL | BSD-3-Clause (ver `tools/empacotar/LICENCA-libjxl.txt`) | Incluído no pacote Windows |
| Openverse API | Pesquisa de imagens com licenças abertas (Creative Commons) | API/código MIT; cada imagem mantém a sua licença CC | Serviço externo consultado a pedido do utilizador |
| PyInstaller | Gera o executável Windows | GPL-2.0-or-later, com exceção | Só construção |
| Inno Setup | Gera o instalador Windows | Licença própria do Inno Setup, gratuita | Só construção |
| pytest | Testes | MIT | Só desenvolvimento |
| GCompris | Jogo educativo para crianças. Autores: Timothée Giet e outros | AGPL-3.0 | Não incluído: descarregado do site oficial (gcompris.net), com verificação SHA-256 |
| Simon Tatham's Portable Puzzle Collection (40 jogos) | Coleção completa de 40 jogos de lógica (Black Box, Bridges, Cube, Dominosa, Fifteen, Filling, Flip, Flood, Galaxies, Guess, Inertia, Keen, Light Up, Loopy, Magnets, Map, Mines, Mosaic, Net, Netslide, Palisade, Pattern, Pearl, Pegs, Range, Rectangles, Same Game, Signpost, Singles, Sixteen, Slant, Solo, Tents, Towers, Tracks, Twiddle, Undead, Unequal, Unruly e Untangle). Copyright Simon Tatham e outros contribuidores | MIT | Não incluídos: descarregados do site oficial (chiark.greenend.org.uk/~sgtatham/puzzles), com verificação SHA-256 |
| `Resources/Games/simon-*/screenshots/thumb.png` | Miniaturas dos 40 jogos de Simon Tatham no catálogo | Copyright Simon Tatham e outros contribuidores (coleção MIT) | Incluídas, obtidas do site oficial |

## Obrigações ao distribuir

- Incluir este ficheiro em qualquer pacote distribuído.
- **LGPL (PySide6):** manter os avisos de copyright e disponibilizar o texto da licença. No executável Windows, indicar como obter o código-fonte do PySide6 e permitir a substituição da biblioteca. *Confirmar o texto exato antes da primeira publicação.*
- **BSD-3-Clause (libjxl):** incluir o aviso de copyright e o texto da licença (`tools/empacotar/LICENCA-libjxl.txt`) ao distribuir os binários `cjxl` e `djxl`.
- **Jogos:** não são distribuídos com o Quadro. O catálogo indica a fonte oficial, os autores e a licença de cada um, e só descarrega o que o utilizador pede (com verificação SHA-256).
- **Imagens Openverse:** respeitar a licença Creative Commons e a atribuição indicadas pela Openverse para cada imagem obtida.
