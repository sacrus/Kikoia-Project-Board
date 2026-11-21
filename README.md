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

Lista completa das ferramentas externas, com licenças e obrigações ao distribuir: [CREDITOS.md](CREDITOS.md).

## Recomendações para pais e educadores

- **Controlo do correio só dentro do Quadro:** as regras aplicam-se ao programa do Quadro. Se a criança usar o webmail no navegador ou outro dispositivo, as regras não se aplicam. Usa também os controlos parentais do fornecedor do correio ou do sistema, quando existirem.
- **Conta de correio própria para a criança:** não uses a conta principal do adulto. Assim, as regras controlam apenas o correio que a criança recebe e envia.
- **Anexos executáveis:** ficheiros como `.exe`, `.bat`, `.ps1` ou `.msi` pedem sempre a palavra-passe de supervisor, mesmo de remetentes permitidos.
- **Ligações:** só abrem texto de domínios aprovados. As restantes ficam marcadas como bloqueadas.
- **Limitação atual:** as regras, a palavra-passe de supervisor e o ficheiro de regras ficam na pasta do próprio utilizador. Quem entra nessa conta consegue alterá-los. A alteração para uma pasta protegida está prevista e ainda não foi feita.
- **Estado:** as regras do correio estão implementadas, mas a interface do correio ainda não está disponível nesta versão.
