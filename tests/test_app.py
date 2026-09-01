"""
Testes automatizados do backend do Monopoly Quântico.

Rodar com:
    pytest tests/ -v

Nota: estes testes não requerem GROQ_API_KEY nem acesso ao Yahoo Finance —
usam mocks para isolar a lógica de negócio das dependências externas.
"""

import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as app_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _client():
    app_module.app.testing = True
    return app_module.app.test_client()


# ---------------------------------------------------------------------------
# Dado quântico
# ---------------------------------------------------------------------------

def test_quantum_dice_roll_within_range():
    """O dado quântico nunca deve sair do intervalo [1, sides]."""
    for _ in range(30):
        result = app_module.quantum_dice_roll(6)
        assert 1 <= result <= 6


def test_quantum_dice_roll_custom_sides():
    """Funciona também para números de faces diferentes de 6 (ex: dado de 4 lados)."""
    for _ in range(20):
        result = app_module.quantum_dice_roll(4)
        assert 1 <= result <= 4


# ---------------------------------------------------------------------------
# Tabuleiro
# ---------------------------------------------------------------------------

def test_board_has_twelve_tiles():
    assert len(app_module.BOARD) == 12


def test_board_has_four_corners_and_eight_assets():
    corners = [t for t in app_module.BOARD if t["type"] == "corner"]
    assets = [t for t in app_module.BOARD if t["type"] == "asset"]
    assert len(corners) == 4
    assert len(assets) == 8


def test_board_positions_are_sequential():
    positions = [t["pos"] for t in app_module.BOARD]
    assert positions == list(range(12))


# ---------------------------------------------------------------------------
# Métricas financeiras
# ---------------------------------------------------------------------------

def test_moving_average_none_before_window():
    closes = [100, 101, 102, 103, 104]
    sma3 = app_module._moving_average(closes, window=3)
    assert sma3[0] is None
    assert sma3[1] is None
    assert sma3[2] == 101  # média de 100, 101, 102


def test_annualized_volatility_zero_for_flat_prices():
    """Preço constante não deve gerar volatilidade (retornos diários todos zero)."""
    closes = [100.0] * 10
    vol = app_module._annualized_volatility_pct(closes)
    assert vol == 0.0


def test_compute_metrics_returns_expected_keys():
    closes = [100 + i for i in range(60)]
    metrics = app_module.compute_metrics(closes)
    assert set(metrics.keys()) == {"sma20", "sma50", "volatility_pct", "high", "low", "avg_volume"}
    assert metrics["high"] == max(closes)
    assert metrics["low"] == min(closes)


# ---------------------------------------------------------------------------
# Rotas HTTP
# ---------------------------------------------------------------------------

def test_index_route_ok():
    client = _client()
    response = client.get("/")
    assert response.status_code == 200


def test_board_route_returns_json_list():
    client = _client()
    response = client.get("/api/board")
    assert response.status_code == 200
    assert len(response.json) == 12


def test_roll_route_returns_valid_result():
    client = _client()
    response = client.get("/api/roll")
    assert response.status_code == 200
    assert 1 <= response.json["result"] <= 6


def test_asset_route_falls_back_to_synthetic_when_yfinance_fails():
    """Quando o Yahoo Finance não responde (ex: rede bloqueada), o endpoint não deve quebrar —
    deve retornar dados sintéticos com o campo 'source' identificando isso."""
    client = _client()
    response = client.get("/api/asset/TICKER_INEXISTENTE_XYZ")
    assert response.status_code == 200
    assert "source" in response.json
    assert "sma20" in response.json


# ---------------------------------------------------------------------------
# Rota de análise via IA (com mock da Groq)
# ---------------------------------------------------------------------------

def test_analyze_without_api_key_returns_friendly_message():
    original = app_module._groq
    app_module._groq = None
    try:
        client = _client()
        response = client.post("/api/analyze", json={"ticker": "AAPL", "decision": "buy"})
        assert response.status_code == 200
        assert response.json["available"] is False
        assert "GROQ_API_KEY" in response.json["analysis"]
    finally:
        app_module._groq = original


def test_analyze_with_mocked_groq_returns_text():
    original = app_module._groq
    mock_message = MagicMock(content="Análise de teste gerada pelo mock.")
    mock_choice = MagicMock(message=mock_message)
    mock_response = MagicMock(choices=[mock_choice])

    app_module._groq = MagicMock()
    app_module._groq.chat.completions.create.return_value = mock_response

    try:
        client = _client()
        payload = {"ticker": "AAPL", "decision": "buy", "price": 200.0, "change_pct": 5.0}
        response = client.post("/api/analyze", json=payload)
        assert response.status_code == 200
        assert response.json["available"] is True
        assert response.json["analysis"] == "Análise de teste gerada pelo mock."
    finally:
        app_module._groq = original


def test_analyze_cache_avoids_duplicate_api_calls():
    """A mesma decisão sobre o mesmo ativo, com os mesmos números, não deve gerar
    uma segunda chamada real à API — deve vir do cache."""
    original = app_module._groq
    original_cache = app_module._ANALYSIS_CACHE.copy()
    app_module._ANALYSIS_CACHE.clear()

    mock_message = MagicMock(content="Resposta única.")
    mock_choice = MagicMock(message=mock_message)
    mock_response = MagicMock(choices=[mock_choice])

    app_module._groq = MagicMock()
    app_module._groq.chat.completions.create.return_value = mock_response

    try:
        client = _client()
        payload = {"ticker": "MSFT", "decision": "sell", "price": 300.0, "change_pct": -2.0}

        r1 = client.post("/api/analyze", json=payload)
        r2 = client.post("/api/analyze", json=payload)

        assert r1.json["cached"] is False
        assert r2.json["cached"] is True
        assert app_module._groq.chat.completions.create.call_count == 1
    finally:
        app_module._groq = original
        app_module._ANALYSIS_CACHE.clear()
        app_module._ANALYSIS_CACHE.update(original_cache)
