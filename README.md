# Monopoly Quântico — Fase 4

Tabuleiro estilo Banco Imobiliário onde o dado é gerado por computação quântica (Qiskit), as casas representam ativos reais do mercado financeiro (Yahoo Finance) com um dashboard completo, cada decisão de compra/venda recebe uma análise crítica gerada por IA (Groq), e agora o patrimônio do jogador reage de verdade a cada decisão.

## O que tem nesta fase

- **Dado quântico**: 1 a 6 qubits em superposição (porta Hadamard) → medição → colapso em um número de 1 a 6, com rejeição de amostragem pra manter distribuição uniforme.
- **Tabuleiro de 12 casas**: 4 cantos especiais (Partida, Bônus Quântico, Parada Livre, Correção de Mercado) + 8 casas de ativos (AAPL, MSFT, TSLA, PETR4.SA, BTC-USD, NVDA, AMZN, GOOGL).
- **Dados reais via Yahoo Finance**: ao cair numa casa de ativo, busca preço atual e histórico dos últimos 6 meses.
- **Dashboard financeiro**: gráfico com preço + médias móveis de 20/50 dias, volatilidade anualizada, máxima/mínima do período e volume médio.
- **Análise via IA**: ao clicar em comprar ou vender, o backend monta um prompt com os dados reais do ativo e a decisão tomada, chama a API da Groq (modelo `openai/gpt-oss-20b`, open source, gratuito) e retorna uma análise crítica de 3-4 frases — sem dar conselho definitivo, só comentando os prós e riscos da decisão à luz dos números.
- **Patrimônio dinâmico + Carteira de Investimento (novo na Fase 4)**: o modal do ativo tem um seletor de quantidade de cotas **inteiras** (digitável ou com botões +/-), com o custo estimado atualizando em tempo real; comprar investe exatamente a quantidade escolhida (limitada ao caixa disponível — se pedir mais do que cabe, ajusta automaticamente pro máximo possível), e vender agora suporta **venda parcial** (vender só uma parte da posição, mantendo o resto com o mesmo custo médio) além de venda total. O card de patrimônio no topo reflete o valor total em tempo real após cada transação, e o botão "📁 carteira" abre um painel detalhado mostrando caixa disponível, valor investido, patrimônio total e cada posição aberta (ticker, número de cotas, custo médio pago, valor investido naquela posição).
- **Cache de análises (novo na Fase 4)**: o backend guarda em memória a análise gerada para cada combinação de ativo + decisão + preço, então repetir a mesma jogada não gasta uma nova chamada à API — só o primeiro clique bate na Groq de verdade.

## Setup

```bash
pip install flask yfinance qiskit qiskit-aer groq
```

### Configurando a chave da API (obrigatório para a análise via IA)

1. Crie uma conta grátis em [console.groq.com](https://console.groq.com) (sem cartão de crédito)
2. Vá em **API Keys** no menu lateral → **Create API Key**
3. Copie a chave (formato `gsk_...`) — ela só aparece uma vez
4. Configure a variável de ambiente antes de rodar o servidor:

```bash
# Windows (PowerShell)
$env:GROQ_API_KEY="sua-chave-aqui"

# Windows (cmd)
set GROQ_API_KEY=sua-chave-aqui

# Linux/Mac
export GROQ_API_KEY="sua-chave-aqui"
```

Se a chave não estiver configurada, o jogo continua funcionando normalmente (dado, tabuleiro, dashboard) — só a análise via IA mostra uma mensagem explicando que a chave não foi encontrada, em vez de travar o app.

```bash
python app.py
```

Acesse `http://127.0.0.1:5000` no navegador.

## Nota importante sobre o Yahoo Finance

O código tenta buscar dados reais via `yfinance`. Se a chamada falhar por qualquer motivo (rede bloqueada, rate limit, ticker inválido), o backend cai automaticamente num **fallback com dados sintéticos** (gerados com seed fixa por ticker, só pra manter a demo jogável) e sinaliza isso tanto na resposta da API (`"source": "synthetic"`) quanto na interface. Isso foi necessário porque o ambiente onde este código foi desenvolvido bloqueia o domínio do Yahoo Finance — no seu ambiente local, com internet normal, os dados reais devem vir direto sem cair no fallback. Vale testar isso primeiro ao rodar.

## Arquitetura

```
monopoly_quantico/
├── app.py                  # Flask: rotas /api/roll, /api/board, /api/asset/<ticker>, /api/analyze
├── templates/
│   └── index.html          # estrutura do tabuleiro e modal
└── static/
    ├── style.css            # identidade visual (paleta quântica + sinais de mercado)
    └── script.js             # lógica do jogo: mover peão, abrir modal, desenhar gráfico, chamar análise
```

## Próximos passos (extras não implementados)

- Animação de peão andando casa a casa — na verdade **já existe** desde a Fase 1 (o token se move tile a tile com uma pequena pausa entre cada um); ficou registrado por engano como pendente numa versão anterior deste README.
- Multiplayer local (2 jogadores revezando) — discutido, mas não priorizado nesta rodada de melhorias.
- Reavaliação do patrimônio a preço de mercado entre jogadas (hoje ele só muda no momento da compra/venda — ver decisão de design abaixo).

## Decisões de design

- Dado limitado a 1-6 (como um dado convencional) em vez do "0-6" mencionado na ideia original — interpretei como equivalente ao dado padrão de tabuleiro; se a intenção era realmente 7 valores (0 a 6), é só trocar `quantum_dice_roll(6)` por `quantum_dice_roll(7)` e ajustar a lógica de movimento pra aceitar 0 casas (ficar parado).
- Paleta escura com violeta neon (tema quântico) e verde/vermelho pra ganho/perda (convenção de mercado financeiro) — evitei o visual "cream + terracota" que é o padrão genérico de design gerado por IA.
- **Provedor de LLM: Groq**, escolhido em vez da API paga da Anthropic por ser gratuito (sem cartão de crédito) e rodar modelos open source de verdade, o que combina melhor com o espírito do projeto. O modelo inicial (`llama-3.3-70b-versatile`) foi descontinuado durante o desenvolvimento — trocado para `openai/gpt-oss-20b` após consultar a lista de modelos disponíveis via `/v1/models`. Se esse também sair de linha no futuro, é só trocar a constante `_GROQ_MODEL` em `app.py`.
- A análise não recomenda comprar/vender — ela comenta a decisão já tomada pelo jogador, com prós e riscos, pra manter o caráter educativo sem soar como recomendação financeira real.
- **Modelo de patrimônio (Fase 4)**: o "patrimônio" mostrado no topo é caixa + valor investido a **preço de custo** (não a preço de mercado atual). Ou seja, comprar uma ação não muda o patrimônio total (só troca caixa por uma posição de mesmo valor); só a **venda** realiza o lucro ou prejuízo, comparando o preço de custo médio com o preço de venda. Isso foi uma escolha deliberada de simplicidade — reavaliar a carteira a mercado a cada jogada exigiria buscar o preço atualizado de *todos* os ativos em carteira a cada rolagem de dado, não só do ativo da casa atual, o que multiplicaria as chamadas ao Yahoo Finance sem necessidade para o propósito educativo do jogo.
- **Cache de análises (Fase 4)**: implementado em memória (um dicionário do processo Python), não em disco nem banco de dados — então ele reseta toda vez que o servidor é reiniciado. Isso é suficiente para uma sessão de jogo, mas não persiste entre partidas diferentes.
- **Cotas sempre inteiras**: o jogo não simula ações fracionárias (fractional shares) — se o usuário digita `22.195`, o valor é truncado para `22` (não arredondado para `23`), tanto na compra quanto na venda. Isso reflete a mecânica mais comum de corretoras tradicionais, embora fractional shares existam de verdade em algumas plataformas modernas — decisão de simplicidade pra manter a carteira sempre com números redondos e fáceis de ler.
