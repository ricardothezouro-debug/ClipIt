# ClipIt

> **Beta.** O fluxo inteiro só se prova ao vivo, e ainda não foi. Se algo
> não funcionar na sua live, abra uma issue com o que apareceu na tela.

Cria o clipe na Twitch do que **acabou de acontecer** e guarda o link junto da
sua marcação. Plugin do [Streamer Sidekick](https://github.com/ricardothezouro-debug/streamer_sidekick).

Você aperta o atalho, e três coisas acontecem:

1. a Twitch cria o clipe;
2. a marcação vai para o seu arquivo do Marcador, no formato de sempre;
3. o link do clipe vai colado nela.

No fim da live, `[16:48:03] morri` virou
`[16:48:03] morri — https://clips.twitch.tv/AbcXyz`, e a aba **Pauta de cortes**
é a lista de tarefas da edição, montada sozinha enquanto você jogava.

## Instalação

Pelo marketplace do Streamer Sidekick (o card **+**). Depois, em
**Configurações**:

1. conecte sua conta da Twitch;
2. escolha um **atalho global** — é ele que você vai usar no meio do jogo.

Escolha uma combinação que o Marcador e o Contador não usem: o Sidekick não
detecta conflito com atalhos de plugin.

## Como o login funciona

Pelo **Device Code Grant Flow**: o plugin mostra um código curto, você digita em
`twitch.tv/activate` e autoriza no navegador. Nenhuma senha passa pelo plugin.

Escolhemos esse fluxo porque este repositório é público. O fluxo de
Authorization Code exigiria um `client_secret`, que viraria público no primeiro
push — e segredo publicado não é segredo. O device code não usa secret para
clientes públicos.

O acesso concedido é só `clips:edit`: criar clipes, e nada além disso.

## O que a API da Twitch permite (e o que não permite)

Vale saber antes de usar, para nada parecer defeito:

| | |
|---|---|
| Duração do clipe | **Você não escolhe.** A Twitch pega ~30s do que passou. Dá para ajustar depois, no link de edição. |
| Título | Não dá para definir na criação. O clipe nasce com o nome padrão da Twitch; o seu texto fica na sua marcação. |
| Estar ao vivo | Obrigatório. Sem transmissão no ar, não há o que clipar. |
| Processamento | Até ~15s. O **link não espera** por isso: ele sai do id que a Twitch devolve na hora. |

## O momento que entra no clipe

Sua live chega ao espectador com uns 15 segundos de atraso, e dá para escolher
qual dos dois momentos capturar:

- **O que eu acabei de fazer** — para quando você clipa reagindo ao jogo.
- **O que o chat acabou de ver** — para quando você clipa porque o chat reagiu.

## Desenvolvimento

```bash
python -m venv .venv && ./.venv/bin/pip install pytest PySide6
./.venv/bin/python -m pytest -q
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ./.venv/bin/python scripts/smoke_test.py
```

O `core/` não importa PySide6 e não toca a rede nos testes — há guarda-corpos
por AST que garantem isso, além de simularem o build congelado do Sidekick,
onde um import de terceiro esquecido faria o plugin instalar e nunca abrir.
