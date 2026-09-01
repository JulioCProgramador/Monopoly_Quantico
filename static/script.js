const boardEl = document.getElementById("board");
const dieEl = document.getElementById("die");
const dieFaceEl = document.getElementById("die-face");
const rollBtn = document.getElementById("roll-btn");
const logEl = document.getElementById("log");

const modalOverlay = document.getElementById("modal-overlay");
const modalTicker = document.getElementById("modal-ticker");
const modalPrice = document.getElementById("modal-price");
const modalChange = document.getElementById("modal-change");
const modalChart = document.getElementById("modal-chart");
const modalSource = document.getElementById("modal-source");
const modalAnalysis = document.getElementById("modal-analysis");
const qtyInput = document.getElementById("qty-input");
const qtyCostEl = document.getElementById("qty-cost");
const qtyOwnedEl = document.getElementById("qty-owned");

const walletValueEl = document.getElementById("wallet-value");
const walletBtn = document.getElementById("wallet-btn");
const walletModalOverlay = document.getElementById("wallet-modal-overlay");
const walletCashEl = document.getElementById("wallet-cash");
const walletInvestedEl = document.getElementById("wallet-invested");
const walletTotalEl = document.getElementById("wallet-total");
const holdingsListEl = document.getElementById("holdings-list");

let board = [];
let playerPos = 0;
let currentAsset = null; // guarda os dados do ativo aberto no modal, usado pela análise via IA

// ---------- Carteira ----------

const STARTING_CASH = 10000;
const STAKE_PER_BUY = 1000; // valor investido a cada decisão de compra (limitado ao caixa disponível)

let cash = STARTING_CASH;
let holdings = {}; // ticker -> { shares, avgCost }

function formatMoney(v) {
  return v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function investedAtCost() {
  return Object.values(holdings).reduce((sum, h) => sum + h.shares * h.avgCost, 0);
}

function netWorth() {
  // Patrimônio = caixa + valor investido a preço de custo (não reavalia a mercado entre jogadas).
  return cash + investedAtCost();
}

function updateWalletDisplay() {
  walletValueEl.textContent = `$ ${formatMoney(netWorth())}`;
  if (walletModalOverlay.classList.contains("open")) {
    renderWalletModal(); // mantém o modal em sincronia se estiver aberto durante uma decisão
  }
}

// ---------- Modal da carteira ----------

walletBtn.addEventListener("click", () => {
  renderWalletModal();
  walletModalOverlay.classList.add("open");
});

document.getElementById("wallet-modal-close").addEventListener("click", () => {
  walletModalOverlay.classList.remove("open");
});

function renderWalletModal() {
  walletCashEl.textContent = `$ ${formatMoney(cash)}`;
  walletInvestedEl.textContent = `$ ${formatMoney(investedAtCost())}`;
  walletTotalEl.textContent = `$ ${formatMoney(netWorth())}`;

  const tickers = Object.keys(holdings);
  if (tickers.length === 0) {
    holdingsListEl.innerHTML = `<p class="holdings-empty">nenhuma posição ainda — compre um ativo caindo numa casa do tabuleiro.</p>`;
    return;
  }

  holdingsListEl.innerHTML = tickers.map(ticker => {
    const h = holdings[ticker];
    const value = h.shares * h.avgCost;
    return `
      <div class="holding-row">
        <div class="holding-info">
          <span class="holding-ticker">${ticker}</span>
          <span class="holding-shares">${h.shares} cotas</span>
        </div>
        <div class="holding-value">
          <span class="holding-cost">$ ${formatMoney(value)}</span>
          <span class="holding-avg">custo médio: $ ${h.avgCost.toFixed(2)}</span>
        </div>
      </div>
    `;
  }).join("");
}

// ---------- Inicialização ----------

async function init() {
  const res = await fetch("/api/board");
  board = await res.json();
  renderBoard();
}

function renderBoard() {
  boardEl.innerHTML = "";
  board.forEach(tile => {
    const el = document.createElement("div");
    el.className = `tile ${tile.type}`;
    el.style.gridArea = `t${tile.pos}`;
    el.id = `tile-${tile.pos}`;

    if (tile.type === "corner") {
      el.innerHTML = `
        <span class="tile-icon">${tile.icon}</span>
        <span class="tile-name">${tile.name}</span>
      `;
    } else {
      el.innerHTML = `
        <span class="tile-name">${tile.name}</span>
        <span class="tile-ticker">${tile.ticker}</span>
      `;
    }
    boardEl.appendChild(el);
  });
  placeToken();
}

function placeToken() {
  document.querySelectorAll(".token").forEach(t => t.remove());
  document.querySelectorAll(".tile").forEach(t => t.classList.remove("active-tile"));

  const currentTile = document.getElementById(`tile-${playerPos}`);
  currentTile.classList.add("active-tile");
  const token = document.createElement("div");
  token.className = "token";
  currentTile.appendChild(token);
}

// ---------- Dado quântico ----------

rollBtn.addEventListener("click", handleRoll);

async function handleRoll() {
  rollBtn.disabled = true;
  dieEl.classList.remove("collapsing");
  void dieEl.offsetWidth; // reset da animação
  dieEl.classList.add("collapsing");
  dieFaceEl.textContent = "…";

  const res = await fetch("/api/roll");
  const data = await res.json();
  const steps = data.result;

  setTimeout(async () => {
    dieFaceEl.textContent = steps;
    log(`⚛ colapso quântico → ${steps}`);
    await moveToken(steps);
    rollBtn.disabled = false;
  }, 900);
}

async function moveToken(steps) {
  for (let i = 0; i < steps; i++) {
    playerPos = (playerPos + 1) % board.length;
    placeToken();
    await sleep(220);
  }

  const tile = board[playerPos];
  log(`📍 caiu em: ${tile.name}`);

  if (tile.type === "asset") {
    await openAssetModal(tile);
  } else {
    log(`— casa especial, sem ativo por aqui.`);
  }
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

// ---------- Modal do ativo ----------

async function openAssetModal(tile) {
  modalTicker.textContent = tile.ticker;
  modalPrice.textContent = "carregando…";
  modalChange.textContent = "";
  modalChart.innerHTML = "";
  modalSource.textContent = "buscando dados…";
  resetAnalysisPanel();
  setDecisionButtonsEnabled(true);

  modalOverlay.classList.add("open");

  const res = await fetch(`/api/asset/${tile.ticker}`);
  const data = await res.json();
  currentAsset = data; // fica disponível pros botões comprar/vender chamarem a análise

  modalPrice.textContent = `$ ${data.price.toFixed(2)}`;
  const up = data.change_pct >= 0;
  modalChange.textContent = `${up ? "+" : ""}${data.change_pct}% (6m)`;
  modalChange.className = `modal-change ${up ? "up" : "down"}`;
  modalSource.textContent = data.source === "yahoo_finance"
    ? "fonte: Yahoo Finance — últimos 6 meses"
    : "fonte: dados sintéticos (demo — Yahoo Finance indisponível neste ambiente)";

  fillStats(data);
  drawChart(data.history, data.sma20, data.sma50);
  initQtyControl();
}

function initQtyControl() {
  const price = currentAsset.price;

  // Sugestão inicial: quantas cotas INTEIRAS dariam pra comprar com um aporte de referência de
  // $1.000 (limitado ao caixa disponível), só como ponto de partida — o usuário pode digitar outro valor.
  const suggested = Math.floor(Math.min(STAKE_PER_BUY, cash) / price);
  qtyInput.value = suggested > 0 ? suggested : 0;
  qtyInput.step = "1";
  qtyInput.min = "0";

  updateQtyMeta();
}

function wholeShares(v) {
  return Math.floor(v); // cotas são sempre números inteiros — trunca em vez de arredondar pra cima
}

function updateQtyMeta() {
  if (!currentAsset) return;
  const qty = wholeShares(parseFloat(qtyInput.value)) || 0;
  const cost = qty * currentAsset.price;
  const owned = holdings[currentAsset.ticker]?.shares || 0;

  qtyCostEl.textContent = `≈ $ ${formatMoney(cost)}`;
  qtyOwnedEl.textContent = owned > 0 ? `você possui: ${owned}` : "você não possui este ativo";
}

qtyInput.addEventListener("input", updateQtyMeta);

document.getElementById("qty-dec").addEventListener("click", () => {
  const current = wholeShares(parseFloat(qtyInput.value)) || 0;
  qtyInput.value = Math.max(0, current - 1);
  updateQtyMeta();
});

document.getElementById("qty-inc").addEventListener("click", () => {
  const current = wholeShares(parseFloat(qtyInput.value)) || 0;
  qtyInput.value = current + 1;
  updateQtyMeta();
});

function fillStats(data) {
  document.getElementById("stat-vol").textContent = `${data.volatility_pct}%`;
  document.getElementById("stat-high").textContent = `$ ${data.high.toFixed(2)}`;
  document.getElementById("stat-low").textContent = `$ ${data.low.toFixed(2)}`;
  document.getElementById("stat-volume").textContent = data.avg_volume
    ? formatVolume(data.avg_volume)
    : "—";
}

function formatVolume(v) {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
  return `${v}`;
}

function drawChart(history, sma20, sma50) {
  const w = 400, h = 120, pad = 6;

  // Escala compartilhada: considera preço + as duas médias móveis (ignorando os nulls do início)
  const allValues = [...history, ...(sma20 || []), ...(sma50 || [])].filter(v => v != null);
  const min = Math.min(...allValues);
  const max = Math.max(...allValues);
  const range = max - min || 1;

  const toPoints = series => series
    .map((v, i) => {
      if (v == null) return null;
      const x = pad + (i / (history.length - 1)) * (w - pad * 2);
      const y = h - pad - ((v - min) / range) * (h - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .filter(Boolean)
    .join(" ");

  const up = history[history.length - 1] >= history[0];
  const priceColor = up ? "#22C55E" : "#F43F5E";

  const pricePoints = toPoints(history);
  const sma20Points = sma20 ? toPoints(sma20) : "";
  const sma50Points = sma50 ? toPoints(sma50) : "";

  modalChart.innerHTML = `
    ${sma50Points ? `<polyline points="${sma50Points}" fill="none" stroke="#8B5CF6" stroke-width="1.4" stroke-dasharray="3 3" opacity="0.8" />` : ""}
    ${sma20Points ? `<polyline points="${sma20Points}" fill="none" stroke="#EAB308" stroke-width="1.4" opacity="0.85" />` : ""}
    <polyline points="${pricePoints}" fill="none" stroke="${priceColor}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
  `;
}

document.getElementById("modal-close").addEventListener("click", closeModal);
document.getElementById("btn-skip").addEventListener("click", closeModal);

document.getElementById("btn-buy").addEventListener("click", () => handleDecision("buy"));
document.getElementById("btn-sell").addEventListener("click", () => handleDecision("sell"));

async function handleDecision(decision) {
  if (!currentAsset) return;

  const executed = applyTransaction(decision);
  if (!executed) {
    modalAnalysis.innerHTML = `<p class="analysis-unavailable">nenhuma transação foi registrada — ajuste a quantidade e tente de novo.</p>`;
    return;
  }
  updateQtyMeta();

  setDecisionButtonsEnabled(false);
  renderAnalysisLoading();

  try {
    const res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ticker: currentAsset.ticker,
        decision,
        price: currentAsset.price,
        change_pct: currentAsset.change_pct,
        volatility_pct: currentAsset.volatility_pct,
        high: currentAsset.high,
        low: currentAsset.low,
        sma20: lastValid(currentAsset.sma20),
        sma50: lastValid(currentAsset.sma50),
      }),
    });
    const data = await res.json();
    renderAnalysisResult(data.analysis, data.available);
  } catch (err) {
    renderAnalysisResult("Não foi possível conectar ao servidor de análise agora.", false);
  }
}

function applyTransaction(decision) {
  const ticker = currentAsset.ticker;
  const price = currentAsset.price;
  const typedQty = parseFloat(qtyInput.value);
  let qty = wholeShares(typedQty); // trunca pra baixo — cotas são sempre inteiras (22.195 -> 22)

  if (!qty || qty <= 0) {
    log(`⚠️ digite uma quantidade de cotas válida (número inteiro) antes de ${decision === "buy" ? "comprar" : "vender"}.`);
    return false;
  }

  if (typedQty !== qty) {
    log(`ℹ️ quantidade ajustada para ${qty} cotas inteiras (não é possível comprar/vender frações de ação).`);
  }

  if (decision === "buy") {
    const maxAffordable = Math.floor(cash / price);
    if (qty > maxAffordable) {
      qty = maxAffordable;
      log(`⚠️ caixa insuficiente para a quantidade pedida — ajustado para o máximo comprável (${qty} cotas).`);
    }
    if (qty <= 0) {
      log(`⚠️ caixa insuficiente para comprar nem 1 cota de ${ticker}.`);
      return false;
    }

    const amount = qty * price;
    cash -= amount;

    if (holdings[ticker]) {
      const existing = holdings[ticker];
      const totalShares = existing.shares + qty;
      const totalCost = existing.shares * existing.avgCost + amount;
      holdings[ticker] = { shares: totalShares, avgCost: totalCost / totalShares };
    } else {
      holdings[ticker] = { shares: qty, avgCost: price };
    }

    log(`🟢 comprou ${qty} cotas de ${ticker} por $ ${formatMoney(amount)} (a $ ${price.toFixed(2)}/cota)`);
  } else if (decision === "sell") {
    const position = holdings[ticker];
    const owned = position?.shares || 0;

    if (owned <= 0) {
      log(`🔴 tentou vender ${ticker}, mas não possui cotas desse ativo na carteira.`);
      return false;
    }

    if (qty > owned) {
      qty = owned;
      log(`⚠️ quantidade pedida maior que a posição — ajustado para vender tudo (${qty} cotas).`);
    }

    const proceeds = qty * price;
    const gain = proceeds - qty * position.avgCost;
    cash += proceeds;

    const remaining = owned - qty;
    if (remaining > 0) {
      holdings[ticker] = { shares: remaining, avgCost: position.avgCost };
    } else {
      delete holdings[ticker];
    }

    const gainLabel = gain >= 0 ? `lucro de $ ${formatMoney(gain)}` : `prejuízo de $ ${formatMoney(Math.abs(gain))}`;
    log(`🔴 vendeu ${qty} cotas de ${ticker} por $ ${formatMoney(proceeds)} (${gainLabel})`);
  }

  updateWalletDisplay();
  return true;
}

function lastValid(series) {
  if (!series) return null;
  const values = series.filter(v => v != null);
  return values.length ? values[values.length - 1] : null;
}

function setDecisionButtonsEnabled(enabled) {
  document.getElementById("btn-buy").disabled = !enabled;
  document.getElementById("btn-sell").disabled = !enabled;
}

function resetAnalysisPanel() {
  modalAnalysis.innerHTML = `<p class="analysis-stub" id="analysis-placeholder">compre ou venda para receber uma análise sobre a decisão.</p>`;
}

function renderAnalysisLoading() {
  modalAnalysis.innerHTML = `
    <p class="analysis-loading"><span class="spark">⚛</span> gerando análise com IA…</p>
  `;
}

function renderAnalysisResult(text, available) {
  if (available) {
    modalAnalysis.innerHTML = `
      <span class="analysis-tag">análise via IA</span>
      <p class="analysis-text"></p>
    `;
    modalAnalysis.querySelector(".analysis-text").textContent = text;
  } else {
    modalAnalysis.innerHTML = `<p class="analysis-unavailable"></p>`;
    modalAnalysis.querySelector(".analysis-unavailable").textContent = text;
  }
}

function closeModal() {
  modalOverlay.classList.remove("open");
  currentAsset = null;
}

// ---------- Log ----------

function log(msg) {
  const empty = logEl.querySelector(".log-empty");
  if (empty) empty.remove();
  const p = document.createElement("p");
  p.textContent = msg;
  logEl.prepend(p);
}

init();
updateWalletDisplay();
