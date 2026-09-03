"""
Monopoly Quântico
---------------------------
Backend Flask que expõe:
  - GET  /api/roll            -> resultado do dado quântico (1-6, via Qiskit)
  - GET  /api/board           -> configuração das casas do tabuleiro
  - GET  /api/asset/<ticker>  -> dados reais (Yahoo Finance) dos últimos 6 meses,
                                  com métricas: volatilidade, médias móveis, máx/mín, volume médio
  - POST /api/analyze         -> análise via LLM (Groq) sobre a decisão de compra/venda, com cache

Requisitos:
    pip install flask yfinance qiskit qiskit-aer groq python-dotenv

Variável de ambiente necessária para a Fase 3/4:
    GROQ_API_KEY   (chave gratuita da Groq — console.groq.com/keys)
    Pode vir de um arquivo .env na raiz do projeto (veja .env.example) ou de uma
    variável de ambiente do sistema — o que já estiver configurado tem prioridade.
"""

from flask import Flask, jsonify, render_template, request
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from collections import OrderedDict
from dotenv import load_dotenv
import yfinance as yf
import random
import statistics
import os
from groq import Groq

load_dotenv()  # lê o arquivo .env (se existir) e carrega suas variáveis em os.environ

app = Flask(__name__)
_simulator = AerSimulator()

# Cliente da API da Groq (modelos open source como Llama, gratuitos com rate limit).
# Se a chave não estiver configurada, o cliente fica None e a rota /api/analyze responde
# com uma mensagem explicando como configurar — sem derrubar o app.
_GROQ_MODEL = "openai/gpt-oss-20b"
_groq = Groq() if os.environ.get("GROQ_API_KEY") else None

# Cache simples em memória: mesma decisão (ticker + tipo + preço + variação) não gera nova
# chamada à API. Evita gastar limite de requisições em cliques repetidos ou re-visitas à
# mesma casa com os dados ainda iguais. Tamanho limitado (LRU manual via OrderedDict).
_ANALYSIS_CACHE: "OrderedDict[tuple, str]" = OrderedDict()
_ANALYSIS_CACHE_MAX = 200



# ---------------------------------------------------------------------------
# Dado quântico (mesma lógica do projeto Quantum Coin Flip Casino)
# ---------------------------------------------------------------------------
def quantum_dice_roll(sides: int = 6) -> int:
    """Dado quântico uniforme de 1 a `sides`, via superposição (Hadamard) + rejeição de amostragem."""
    n_qubits = (sides - 1).bit_length()

    while True:
        qc = QuantumCircuit(n_qubits, n_qubits)
        qc.h(range(n_qubits))
        qc.measure(range(n_qubits), range(n_qubits))

        job = _simulator.run(qc, shots=1)
        counts = job.result().get_counts()
        raw_value = int(list(counts.keys())[0], 2)

        if raw_value < sides:
            return raw_value + 1


# ---------------------------------------------------------------------------
# Configuração do tabuleiro — 12 casas (4 cantos especiais + 8 ativos)
# ---------------------------------------------------------------------------
BOARD = [
    {"pos": 0,  "type": "corner", "name": "Partida",        "icon": "🚀"},
    {"pos": 1,  "type": "asset",  "name": "Apple",          "ticker": "AAPL"},
    {"pos": 2,  "type": "asset",  "name": "Microsoft",      "ticker": "MSFT"},
    {"pos": 3,  "type": "corner", "name": "Bônus Quântico", "icon": "⚛️"},
    {"pos": 4,  "type": "asset",  "name": "Tesla",          "ticker": "TSLA"},
    {"pos": 5,  "type": "asset",  "name": "Petrobras",      "ticker": "PETR4.SA"},
    {"pos": 6,  "type": "corner", "name": "Parada Livre",   "icon": "☕"},
    {"pos": 7,  "type": "asset",  "name": "Bitcoin",        "ticker": "BTC-USD"},
    {"pos": 8,  "type": "asset",  "name": "Nvidia",         "ticker": "NVDA"},
    {"pos": 9,  "type": "corner", "name": "Correção de Mercado", "icon": "📉"},
    {"pos": 10, "type": "asset",  "name": "Amazon",         "ticker": "AMZN"},
    {"pos": 11, "type": "asset",  "name": "Google",         "ticker": "GOOGL"},
]


def _moving_average(closes: list[float], window: int) -> list:
    """Média móvel simples. Retorna None nos primeiros `window - 1` pontos (sem dado suficiente)."""
    result = []
    for i in range(len(closes)):
        if i < window - 1:
            result.append(None)
        else:
            result.append(round(sum(closes[i - window + 1: i + 1]) / window, 2))
    return result


def _annualized_volatility_pct(closes: list[float]) -> float:
    """Desvio padrão dos retornos diários, anualizado (≈252 pregões/ano), em %."""
    returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes))]
    if len(returns) < 2:
        return 0.0
    daily_std = statistics.stdev(returns)
    return round(daily_std * (252 ** 0.5) * 100, 2)


def compute_metrics(closes: list[float], volumes: list[float] | None = None) -> dict:
    """Calcula o pacote de métricas do dashboard a partir de uma série de preços de fechamento."""
    return {
        "sma20": _moving_average(closes, 20),
        "sma50": _moving_average(closes, 50),
        "volatility_pct": _annualized_volatility_pct(closes),
        "high": round(max(closes), 2),
        "low": round(min(closes), 2),
        "avg_volume": round(sum(volumes) / len(volumes)) if volumes else None,
    }


def _synthetic_history(ticker: str):
    """Gera uma série sintética plausível para quando o Yahoo Finance não está acessível
    (ex.: ambientes de sandbox sem esse domínio liberado). Usado só como fallback de demonstração."""
    random.seed(ticker)  # mesma "empresa" sempre gera a mesma série fake, pra consistência na demo
    price = random.uniform(50, 400)
    history = []
    volumes = []
    for _ in range(130):  # ~6 meses de pregões
        price *= 1 + random.uniform(-0.03, 0.032)
        history.append(round(price, 2))
        volumes.append(random.randint(2_000_000, 40_000_000))
    change_pct = ((history[-1] - history[0]) / history[0]) * 100
    return {
        "ticker": ticker,
        "price": history[-1],
        "change_pct": round(change_pct, 2),
        "history": history,
        "source": "synthetic (demo — Yahoo Finance indisponível neste ambiente)",
        **compute_metrics(history, volumes),
    }


@app.route("/api/roll")
def api_roll():
    return jsonify({"result": quantum_dice_roll(6)})


@app.route("/api/board")
def api_board():
    return jsonify(BOARD)


@app.route("/api/asset/<ticker>")
def api_asset(ticker):
    try:
        hist = yf.Ticker(ticker).history(period="6mo")
        if hist.empty:
            raise ValueError("histórico vazio")

        closes = hist["Close"].round(2).tolist()
        volumes = hist["Volume"].tolist() if "Volume" in hist else None
        change_pct = ((closes[-1] - closes[0]) / closes[0]) * 100

        return jsonify({
            "ticker": ticker,
            "price": closes[-1],
            "change_pct": round(change_pct, 2),
            "history": closes,
            "source": "yahoo_finance",
            **compute_metrics(closes, volumes),
        })
    except Exception as e:
        # Fallback de demonstração — em produção normal (fora do sandbox) o yfinance funciona direto.
        data = _synthetic_history(ticker)
        data["error"] = str(e)
        return jsonify(data)


@app.route("/")
def index():
    return render_template("index.html")


def _build_analysis_prompt(payload: dict) -> str:
    """Monta o prompt com os dados do ativo e a decisão do usuário, em português."""
    decision_label = {"buy": "COMPROU", "sell": "VENDEU"}.get(payload.get("decision"), "decidiu sobre")

    return f"""Você é um analista financeiro em um jogo de tabuleiro educativo (Monopoly Quântico).
Um jogador acabou de {decision_label} o ativo {payload.get('ticker')} com base nos seguintes dados reais
dos últimos 6 meses:

- Preço atual: $ {payload.get('price')}
- Variação no período: {payload.get('change_pct')}%
- Volatilidade anualizada: {payload.get('volatility_pct')}%
- Máxima do período: $ {payload.get('high')}
- Mínima do período: $ {payload.get('low')}
- Média móvel de 20 dias: $ {payload.get('sma20')}
- Média móvel de 50 dias: $ {payload.get('sma50')}

Escreva uma análise curta (3-4 frases, sem saudação nem despedida) comentando essa decisão à luz
desses dados. Seja direto e didático, aponte tanto pontos a favor quanto riscos da decisão. Não dê
conselho financeiro definitivo ("compre"/"venda") — o jogador já decidiu; o papel aqui é comentar
criticamente a decisão tomada, como um mentor explicando o raciocínio por trás dos números."""


def _cache_key(payload: dict) -> tuple:
    """Chave do cache: mesma decisão sobre o mesmo ativo, com os mesmos números, não repete a chamada."""
    return (
        payload.get("ticker"),
        payload.get("decision"),
        round(float(payload.get("price", 0)), 2),
        round(float(payload.get("change_pct", 0)), 2),
    )


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    payload = request.get_json(force=True) or {}

    if _groq is None:
        return jsonify({
            "analysis": (
                "Análise via IA desativada: defina a variável de ambiente GROQ_API_KEY "
                "(gere uma chave grátis em console.groq.com/keys) e reinicie o servidor para habilitar esta etapa."
            ),
            "available": False,
        })

    key = _cache_key(payload)
    if key in _ANALYSIS_CACHE:
        _ANALYSIS_CACHE.move_to_end(key)  # marca como usado recentemente (LRU)
        return jsonify({"analysis": _ANALYSIS_CACHE[key], "available": True, "cached": True})

    try:
        response = _groq.chat.completions.create(
            model=_GROQ_MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": _build_analysis_prompt(payload)}],
        )
        text = response.choices[0].message.content.strip()

        _ANALYSIS_CACHE[key] = text
        _ANALYSIS_CACHE.move_to_end(key)
        if len(_ANALYSIS_CACHE) > _ANALYSIS_CACHE_MAX:
            _ANALYSIS_CACHE.popitem(last=False)  # remove o item mais antigo

        return jsonify({"analysis": text, "available": True, "cached": False})

    except Exception as e:
        return jsonify({
            "analysis": f"Não foi possível gerar a análise agora ({e}). A decisão foi registrada normalmente.",
            "available": False,
        })


if __name__ == "__main__":
    app.run(debug=True, port=5000)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
