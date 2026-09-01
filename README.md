# ⚛ Monopoly Quântico

**Um tabuleiro estilo Banco Imobiliário onde o dado é gerado por computação quântica real, as casas são ativos de verdade do mercado financeiro, e uma IA comenta cada decisão de investimento do jogador.**

Projeto pessoal desenvolvido para explorar, na prática, a interseção entre computação quântica, engenharia de dados financeiros e IA generativa — três áreas que normalmente aparecem separadas em portfólio, aqui combinadas em uma única aplicação jogável.

---

## 🎮 O que o projeto faz

1. O jogador joga um dado cujo resultado (1 a 6) não vem de `random()` — vem da **medição de qubits em superposição quântica** (porta Hadamard, via Qiskit).
2. O peão anda pelo tabuleiro. Ao cair numa casa de ativo (Apple, Tesla, Bitcoin, Petrobras, etc.), o jogo busca **dados reais dos últimos 6 meses** direto do Yahoo Finance: preço, variação, médias móveis, volatilidade.
3. O jogador escolhe quantas cotas comprar ou vender daquele ativo.
4. Um **modelo de linguagem (LLM)** recebe os números reais da jogada e escreve uma análise crítica de 3-4 frases sobre a decisão — sem recomendar "compre" ou "venda", só comentando prós e riscos à luz dos dados.
5. O patrimônio do jogador (começando em $10.000) reflete cada transação em tempo real, com uma carteira de investimentos detalhada mostrando posição por posição.

---

## 🧰 Stack técnica

| Camada | Tecnologia | Papel no projeto |
|---|---|---|
| Computação quântica | [Qiskit](https://qiskit.org/) + Qiskit Aer | Simula o circuito quântico do dado (porta Hadamard + medição) |
| Backend | Python 3 + [Flask](https://flask.palletsprojects.com/) | Serve a API REST e a página |
| Dados financeiros | [yfinance](https://github.com/ranaroussi/yfinance) | Busca preços e histórico reais do Yahoo Finance |
| IA generativa | [Groq](https://groq.com/) (modelo `openai/gpt-oss-20b`, open source) | Gera a análise crítica de cada decisão |
| Frontend | HTML + CSS + JavaScript vanilla | Sem framework, sem build step — só DOM API nativa |
| Testes | [pytest](https://pytest.org/) | 15 testes automatizados cobrindo lógica de negócio e rotas HTTP |
| Versionamento de dados | [DVC](https://dvc.org/) | Versiona os datasets de exemplo separadamente do código |
| Controle de versão | Git | Histórico do projeto |

---

## 🏗️ Arquitetura

```
monopoly_quantico/
├── app.py                        # Backend Flask: rotas, dado quântico, métricas, integração com IA
├── requirements.txt               # Dependências Python
├── .env.example                   # Documenta a variável de ambiente necessária (sem segredo real)
├── LICENSE                        # MIT
├── templates/
│   └── index.html                 # Estrutura do tabuleiro, modais de ativo e carteira
├── static/
│   ├── style.css                  # Identidade visual (paleta quântica + sinais de mercado)
│   └── script.js                  # Lógica do jogo: movimento, carteira, gráficos, chamadas de API
├── tests/
│   └── test_app.py                # Suíte de testes automatizados (pytest)
└── data/
    └── sample_market_data/        # Datasets de exemplo, versionados via DVC (não pelo Git)
        ├── AAPL.json
        ├── MSFT.json
        └── ... (8 ativos)
```

**Fluxo de uma jogada:**

```
[Jogador clica "jogar o dado"]
          │
          ▼
GET /api/roll ─── Qiskit gera superposição → mede → resultado 1-6
          │
          ▼
[Peão anda casa a casa no tabuleiro]
          │
          ▼
GET /api/asset/<ticker> ─── yfinance busca 6 meses de histórico
          │                  (se falhar: fallback com dados sintéticos)
          ▼
[Dashboard mostra preço, SMA20/50, volatilidade, máx/mín]
          │
          ▼
[Jogador escolhe quantidade e clica comprar/vender]
          │
          ▼
POST /api/analyze ─── monta prompt com dados reais → Groq (LLM)
          │             (cache evita repetir a mesma chamada)
          ▼
[Análise aparece no modal + patrimônio é atualizado]
```

---

## 🚀 Como rodar localmente

### Pré-requisitos
- Python 3.10+
- Uma chave grátis da Groq ([console.groq.com](https://console.groq.com), sem cartão de crédito)

### Passo a passo

```bash
# 1. Clone o repositório
git clone <url-do-seu-repositório>
cd monopoly_quantico

# 2. Crie um ambiente virtual (recomendado)
python -m venv venv
source venv/bin/activate       # Linux/Mac
venv\Scripts\activate          # Windows

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure a chave da API da Groq
cp .env.example .env
# edite o .env e cole sua chave gsk_...
# (ou configure GROQ_API_KEY como variável de ambiente do sistema)

# 5. (Opcional) Recupere os datasets de exemplo versionados via DVC
pip install dvc
dvc pull

# 6. Rode o servidor
python app.py
```

Acesse **http://127.0.0.1:5000** no navegador.

> Sem a chave da Groq configurada, o jogo funciona normalmente (dado, tabuleiro, dashboard) — só a análise via IA mostra uma mensagem explicando que a chave não foi encontrada, em vez de travar o app.

### Rodando os testes

```bash
pytest tests/ -v
```

Os testes usam mocks para a API da Groq e não dependem de internet — rodam isolados, cobrindo desde a uniformidade do dado quântico até o comportamento do cache de análises.

---

## 📦 Por que DVC além do Git?

Código-fonte e dados têm necessidades diferentes de versionamento: arquivos de dados podem crescer, mudar de formato ou ser regenerados, e não faz sentido inflar o histórico do Git com eles. Este projeto usa o [DVC](https://dvc.org/) para versionar os **datasets de exemplo** em `data/sample_market_data/` (usados para testes offline, sem depender do Yahoo Finance estar acessível) — o Git guarda só um arquivo `.dvc` pequeno com o hash dos dados, e o conteúdo real fica num "remote" separado (pode ser uma pasta local, S3, Google Drive, etc.).

```bash
# Reproduzir o dataset em qualquer máquina, depois de clonar o repositório:
dvc pull

# Se os dados de exemplo forem atualizados no futuro:
dvc add data/sample_market_data
git add data/sample_market_data.dvc
git commit -m "Atualiza dataset de exemplo"
dvc push
```

---

## 🧠 Decisões de design que valem destacar

- **Resiliência a falhas externas**: se o Yahoo Finance não responder, o app não quebra — cai automaticamente num fallback com dados sintéticos (gerados com seed fixa, então são reproduzíveis) e sinaliza isso claramente na interface. Se a chave da Groq não estiver configurada, o mesmo princípio se aplica à análise via IA.
- **Cache de análises com chave composta**: a mesma decisão sobre o mesmo ativo, com os mesmos números, não repete a chamada à API — economiza limite de requisições sem arriscar servir uma análise desatualizada se o preço mudou.
- **Cotas sempre inteiras**: quantidades digitadas com casas decimais são truncadas (não arredondadas), refletindo a mecânica de corretoras tradicionais e mantendo a carteira sempre legível.
- **Patrimônio a preço de custo**: comprar uma ação não muda o patrimônio total (só troca caixa por posição de mesmo valor) — só a venda realiza lucro ou prejuízo. Decisão deliberada de simplicidade: reavaliar a carteira a preço de mercado a cada jogada multiplicaria as chamadas ao Yahoo Finance sem necessidade para o propósito do jogo.
- **A IA não dá conselho financeiro definitivo**: o prompt é desenhado pra comentar prós e riscos da decisão já tomada, não pra dizer "compre" ou "venda" — mantém o caráter educativo sem soar como recomendação de investimento real.
- **Zero dependências de visualização**: o gráfico do dashboard é SVG desenhado à mão (três `<polyline>` sobrepostas), sem Chart.js nem D3 — escolha deliberada de manter o frontend enxuto.

---

## 🐛 Desafios reais enfrentados (e como foram resolvidos)

Vale documentar porque isso também é parte do aprendizado do projeto:

- **Modelo de IA descontinuado em produção**: o modelo Llama inicialmente escolhido (`llama-3.3-70b-versatile`) parou de existir na API da Groq durante o desenvolvimento. Diagnosticado consultando o endpoint `/v1/models` da própria API para descobrir o catálogo atual, e resolvido trocando para `openai/gpt-oss-20b`.
- **Variável de ambiente "invisível" no Windows**: configurar `GROQ_API_KEY` como variável permanente no Painel de Controle não bastava — terminais e processos já abertos (inclusive o Windows Terminal, se já estivesse rodando) continuavam com o ambiente antigo em memória. Resolvido isolando o diagnóstico camada por camada (PowerShell → Python interativo → processo do Flask) até confirmar exatamente onde a variável não estava chegando.
- **Cache de arquivo do navegador/Windows**: downloads repetidos de um arquivo com o mesmo nome às vezes salvavam como `arquivo (1).js` em vez de substituir — resultando em versões antigas do JavaScript rodando silenciosamente sem nenhum erro. Resolvido com um processo de "apagar antes de substituir" + hard refresh (`Ctrl+Shift+R`) no navegador.

---

## 🗺️ Possíveis próximos passos

- Multiplayer local (2+ jogadores revezando)
- Reavaliação do patrimônio a preço de mercado (mark-to-market) em vez de preço de custo
- Deploy público (ex: Render, Railway) com um servidor WSGI de produção em vez do servidor de desenvolvimento do Flask
- Persistência de partidas (banco de dados em vez de estado só em memória do navegador)

---

## 📄 Licença

Este projeto está sob a licença MIT — veja o arquivo [LICENSE](./LICENSE).

---

## 👤 Autor

**Julio Cesar Nascimento**
Estudante de Ciência da Computação (UNIP) — buscando oportunidades em analytics, engenharia de dados e IA/ML no setor financeiro/tecnológico.

- GitHub: [github.com/JulioCProgramador](https://github.com/JulioCProgramador)
- LinkedIn: [linkedin.com/in/julio-cesar-nascimento-121738303](https://linkedin.com/in/julio-cesar-nascimento-121738303)
