# Kikoia - Quadro Interativo

Quadro interativo para Windows (com planos futuros para outras plataformas), que funciona de forma independente ou integrado com o teclado Kikoia.

> **Créditos e licenças:** [CREDITOS.md](CREDITOS.md) lista os componentes externos usados, os jogos do catálogo, os seus autores e as obrigações ao distribuir.

## Funcionalidades

- **Quadro de desenho acessível:** menu principal em esferas translúcidas 3D com ícones claros e texto legível, barra contínua para ajustar o tamanho das ferramentas com pré-visualização em tempo real, caneta, borracha, borracha de riscos, formas geométricas, carimbos, pincel mágico, camadas e ferramenta de texto.
- **Menu de definições em cartões:** organização clara entre *Ações do Quadro* e *Aplicações e Ferramentas*, com seleção rápida de tema, idioma e cor de fundo.
- **Imagens e pesquisa segura:** importação de imagens locais (incluindo suporte a JPEG XL com `libjxl`), pesquisa integrada de imagens com licenças abertas através da **Openverse** com galeria moderna e ideias rápidas, e exportação/gravação de projetos (`.kquadro`, JXL, PNG, SVG).
- **Cliente de correio integrado:** interface moderna em 3 painéis com temas claro e escuro, suporte a contas IMAP/POP3/SMTP e OAuth (Google e Microsoft), gestão de contactos com fotos, pastas, rascunhos, leitura em voz alta, anexos (incluindo projetos `.kquadro`) e regras de supervisão para crianças.
- **Catálogo de jogos (43 jogos):** visualização em cartões expansíveis com pesquisa e filtros (tipo, categoria e dispositivos de controlo — rato/touchpad, teclado, caneta virtual e ecrã de toque), transferência direta a partir das fontes oficiais com verificação SHA-256, arranque direto do **GCompris**, os **40 jogos de lógica** da *Simon Tatham's Portable Puzzle Collection* e **2 jogos nativos Kikoia integrados** (*Caminho das Letras* de caligrafia cursiva e *Dedos Musicais* para ecrã de toque).
- **Temas e idiomas sincronizados:** temas Claro/Escuro e **4 idiomas** (`pt-PT`, `en`, `es`, `fr`) centralizados nas Definições do Quadro e sincronizados automaticamente nos dois sentidos com o teclado Kikoia.
- **Integração com o Teclado Kikoia e Android:** ponte local que permite usar o teclado Kikoia e o modo touchpad da aplicação Android diretamente no Quadro.

## Requisitos e execução (desenvolvimento)

- Windows 10 ou 11, Python 3.11 ou superior.

```powershell
cd C:\caminho\para\Board
py -m pip install -r requirements.txt
py -m quadro
```

## Recursos (`Resources/`)

Os recursos são descarregados pelo Quadro apenas quando o utilizador os pede.

- `Resources/index.json`: lista de jogos e ferramentas disponíveis (atualmente 43 jogos). É o único ficheiro lido na abertura.
- `Resources/Games/<jogo>/game.json`: dados do jogo (nome, descrição, autores, copyright, licença, websites, fonte oficial de download e SHA-256).
- `Resources/Games/<jogo>/screenshots/`: imagem inicial (`thumb.png`) e restantes screenshots.
- `Resources/Images/`: imagens usadas pelas ferramentas.

Os jogos de terceiros **não são alojados aqui**: o `game.json` aponta para a fonte oficial, que é de onde o Quadro os descarrega e verifica a integridade por SHA-256.

## Créditos e licenças

| Recurso | Autor / copyright | Licença |
|---|---|---|
| GCompris | Timothée Giet and others | AGPL-3.0 |
| Simon Tatham's Portable Puzzle Collection (40 jogos) | Simon Tatham e outros contribuidores | MIT |
| libjxl (`cjxl`, `djxl`) | The JPEG XL Project Authors | BSD-3-Clause |
| Openverse API | Openverse (WordPress / Creative Commons) | MIT (API); licenças CC por imagem |

Os ficheiros `game.json` de cada jogo indicam os seus próprios créditos e ligações oficiais.

Lista completa das ferramentas externas, com licenças e obrigações ao distribuir: [CREDITOS.md](CREDITOS.md).

## Recomendações para pais e educadores

- **Controlo do correio só dentro do Quadro:** as regras aplicam-se ao cliente de correio do Quadro. Se a criança usar o webmail no navegador ou outro dispositivo, as regras não se aplicam. Usa também os controlos parentais do fornecedor do correio ou do sistema, quando existirem.
- **Conta de correio própria para a criança:** não uses a conta principal do adulto. Assim, as regras controlam apenas o correio que a criança recebe e envia.
- **Anexos executáveis:** ficheiros como `.exe`, `.bat`, `.ps1` ou `.msi` pedem sempre a palavra-passe de supervisor, mesmo de remetentes permitidos.
- **Ligações:** só abrem endereços de domínios aprovados. As restantes ficam marcadas como bloqueadas.
- **Limitação atual:** as regras, a palavra-passe de supervisor e o ficheiro de regras ficam na pasta do próprio utilizador. Quem entra nessa conta consegue alterá-los. A alteração para uma pasta protegida está prevista e ainda não foi feita.
