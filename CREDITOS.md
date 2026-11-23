# Créditos e licenças (Quadro Interativo)

O Quadro usa componentes de terceiros. Cada um mantém a sua própria licença.

**Licença do código do Quadro:** *a definir pelo autor antes da publicação* (ver o ficheiro `CREDITOS.md` do projeto principal, secção «Pontos em aberto»).

## Componentes usados

| Componente | Para que serve | Licença | Como é usado |
|---|---|---|---|
| Python (interpretador) | Corre o programa; vai dentro do executável Windows | PSF-2.0 | Incluído no executável |
| PySide6 e shiboken6 (Qt for Python) | Interface gráfica | LGPL-3.0 (também GPL-2.0 ou GPL-3.0; usamos LGPL-3.0) | Incluído no executável |
| pytest | Testes | MIT | Só desenvolvimento |
| GCompris | Jogo educativo para crianças. Autores: Timothée Giet e outros | AGPL-3.0 | Não incluído: descarregado do site oficial (gcompris.net), com verificação SHA-256 |
| Solo, de Simon Tatham's Portable Puzzle Collection | Jogo de lógica (Sudoku). Copyright Simon Tatham e outros contribuidores | MIT | Não incluído: descarregado do site oficial (chiark.greenend.org.uk/~sgtatham/puzzles), com verificação SHA-256 |
| `Resources/Games/simon-solo/screenshots/thumb.png` | Miniatura do Solo no catálogo | Copyright Simon Tatham (coleção MIT) | Incluída, copiada do site oficial |

## Obrigações ao distribuir

- Incluir este ficheiro em qualquer pacote distribuído.
- **LGPL (PySide6):** manter os avisos de copyright e disponibilizar o texto da licença. No executável Windows, indicar como obter o código-fonte do PySide6 e permitir a substituição da biblioteca. *Confirmar o texto exato antes da primeira publicação.*
- **Jogos:** não são distribuídos com o Quadro. O catálogo indica a fonte oficial e a licença de cada um, e só descarrega o que o utilizador pede.
