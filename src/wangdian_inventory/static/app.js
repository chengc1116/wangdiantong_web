const state = {
  status: null,
  data: null,
  sort: { key: "stock_num", direction: "desc" },
  searchTimer: null,
  chartPoints: [],
  page: 1,
  pageSize: 100,
  warehouseCount: 0,
  activeView: "dashboard",
  dashboardDays: 30,
  warehouseData: [],
  inboundData: null,
  inboundPage: 1,
  inboundPageSize: 100,
  salesData: null,
  salesPage: 1,
  salesPageSize: 100,
  shopSalesData: null,
  shopSalesPage: 1,
  shopSalesPageSize: 100,
  shortData: null,
  shortPage: 1,
  shortPageSize: 100,
  replenishmentData: null,
  replenishmentMode: "normal",
  replenishmentPage: 1,
  replenishmentPageSize: 100,
  purchasePlanData: null,
  purchasePlanPage: 1,
  purchasePlanPageSize: 100,
  transferPlanData: null,
  transferPlanPage: 1,
  transferPlanPageSize: 100,
  clearanceSummaryData: null,
  clearanceSummaryPage: 1,
  clearanceSummaryPageSize: 100,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const numberFormat = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 1 });
const calculationNumberFormat = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 3 });
const currencyFormat = new Intl.NumberFormat("zh-CN", { style: "currency", currency: "CNY", maximumFractionDigits: 0 });
// Purchase prices from WangDian can have up to four decimal places. Keep those
// decimals visible in the clearance view instead of using the dashboard's
// whole-yuan display format.
const clearanceCurrencyFormat = new Intl.NumberFormat("zh-CN", {
  style: "currency",
  currency: "CNY",
  minimumFractionDigits: 0,
  maximumFractionDigits: 4,
});

function localDate(date) {
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 10);
}

function setDefaultDates(days = 30) {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - days + 1);
  $("#startDate").value = localDate(start);
  $("#endDate").value = localDate(end);
}

function setDefaultSalesDates() {
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  const value = localDate(yesterday);
  $("#salesStartDate").value = value;
  $("#salesEndDate").value = value;
  $("#shortStartDate").value = value;
  $("#shortEndDate").value = value;
  $("#shopSalesStartDate").value = value;
  $("#shopSalesEndDate").value = value;
  const inboundStart = new Date(yesterday);
  inboundStart.setDate(inboundStart.getDate() - 6);
  $("#inboundStartDate").value = localDate(inboundStart);
  $("#inboundEndDate").value = value;
  $("#replenishmentEndDate").value = value;
  $("#purchasePlanEndDate").value = value;
  $("#transferPlanEndDate").value = value;
}

function formatNumber(value) {
  return numberFormat.format(Number(value || 0));
}

function formatDays(value) {
  return value === null || value === undefined || value === "" ? "-" : formatNumber(value);
}

function formatDateValue(value) {
  return value || "-";
}

function formatCalculationNumber(value) {
  return calculationNumberFormat.format(Number(value || 0));
}

function formatCurrency(value) {
  return currencyFormat.format(Number(value || 0));
}

function formatClearanceCurrency(value) {
  return clearanceCurrencyFormat.format(Number(value || 0));
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
}

function queryString() {
  const params = new URLSearchParams({
    start: $("#startDate").value,
    end: $("#endDate").value,
  });
  const search = $("#searchInput").value.trim();
  const warehouse = $("#warehouseSelect").value;
  const stockStatus = $("#stockStatusSelect").value;
  if (search) params.set("search", search);
  if (warehouse) params.set("warehouse", warehouse);
  if (stockStatus) params.set("stock_status", stockStatus);
  params.set("page", state.page);
  params.set("page_size", state.pageSize);
  return params.toString();
}

function exportQueryString() {
  const params = new URLSearchParams(queryString());
  params.delete("page");
  params.delete("page_size");
  return params.toString();
}

function salesQueryString() {
  const params = new URLSearchParams({
    start: $("#salesStartDate").value,
    end: $("#salesEndDate").value,
    page: state.salesPage,
    page_size: state.salesPageSize,
  });
  const search = $("#searchInput").value.trim();
  const warehouse = $("#warehouseSelect").value;
  if (search) params.set("search", search);
  if (warehouse) params.set("warehouse", warehouse);
  return params.toString();
}

function inboundQueryString() {
  const params = new URLSearchParams({
    start: $("#inboundStartDate").value,
    end: $("#inboundEndDate").value,
    page: state.inboundPage,
    page_size: state.inboundPageSize,
  });
  const search = $("#searchInput").value.trim();
  const warehouse = $("#warehouseSelect").value;
  const inboundType = $("#inboundTypeSelect").value;
  if (search) params.set("search", search);
  if (warehouse) params.set("warehouse", warehouse);
  if (inboundType) params.set("inbound_type", inboundType);
  return params.toString();
}

function shortQueryString() {
  const params = new URLSearchParams({
    start: $("#shortStartDate").value,
    end: $("#shortEndDate").value,
    page: state.shortPage,
    page_size: state.shortPageSize,
  });
  const search = $("#searchInput").value.trim();
  if (search) params.set("search", search);
  return params.toString();
}

function shopSalesQueryString() {
  const params = new URLSearchParams({
    start: $("#shopSalesStartDate").value,
    end: $("#shopSalesEndDate").value,
    page: state.shopSalesPage,
    page_size: state.shopSalesPageSize,
  });
  const search = $("#searchInput").value.trim();
  const warehouse = $("#warehouseSelect").value;
  const shop = $("#shopSalesShopSelect").value;
  if (search) params.set("search", search);
  if (warehouse) params.set("warehouse", warehouse);
  if (shop) params.set("shop", shop);
  return params.toString();
}

function replenishmentQueryString() {
  const params = new URLSearchParams({
    page: state.replenishmentPage,
    page_size: state.replenishmentPageSize,
    target_days: 30,
    end: $("#replenishmentEndDate").value,
  });
  const search = $("#searchInput").value.trim();
  const warehouse = $("#warehouseSelect").value;
  const alertStatus = $("#alertStatusSelect").value;
  if (search) params.set("search", search);
  if (warehouse) params.set("warehouse", warehouse);
  params.set("alert_mode", state.replenishmentMode);
  if (alertStatus) params.set("alert_status", alertStatus);
  return params.toString();
}

function purchasePlanQueryString() {
  const params = new URLSearchParams({
    page: state.purchasePlanPage,
    page_size: state.purchasePlanPageSize,
    target_days: 30,
    end: $("#purchasePlanEndDate").value,
  });
  const search = $("#searchInput").value.trim();
  const warehouse = $("#warehouseSelect").value;
  const trend = $("#purchaseTrendSelect").value;
  const planStatus = $("#purchaseStatusSelect").value;
  if (search) params.set("search", search);
  if (warehouse) params.set("warehouse", warehouse);
  if (planStatus) params.set("plan_status", planStatus);
  if (trend === "down") { params.set("trend_max", "0.8"); }
  if (trend === "stable") { params.set("trend_min", "0.8"); params.set("trend_max", "1.2"); }
  if (trend === "up") { params.set("trend_min", "1.2"); }
  if (trend === "surge") { params.set("trend_min", "1.8"); }
  return params.toString();
}

function transferPlanQueryString() {
  const params = new URLSearchParams({
    page: state.transferPlanPage,
    page_size: state.transferPlanPageSize,
    end: $("#transferPlanEndDate").value,
  });
  const search = $("#searchInput").value.trim();
  const warehouse = $("#warehouseSelect").value;
  if (search) params.set("search", search);
  if (warehouse) params.set("warehouse", warehouse);
  return params.toString();
}

function clearanceSummaryQueryString() {
  const params = new URLSearchParams({
    page: state.clearanceSummaryPage,
    page_size: state.clearanceSummaryPageSize,
  });
  const search = $("#searchInput").value.trim();
  const warehouse = $("#warehouseSelect").value;
  if (search) params.set("search", search);
  if (warehouse) params.set("warehouse", warehouse);
  return params.toString();
}

async function api(url, options) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || `请求失败 (${response.status})`);
  return body;
}

async function loadStatus() {
  state.status = await api("/api/status");
  const pill = $("#envPill");
  const label = state.status.demo_mode ? "演示数据" : (state.status.environment === "production" ? "正式环境" : "测试环境");
  pill.querySelector("span:last-child").textContent = label;
  pill.classList.toggle("demo", state.status.demo_mode);
  const last = state.status.last_sync;
  $("#lastSync").textContent = last ? `最近同步 ${last.sync_date}` : "尚未同步";
  $("#syncEnvironment").textContent = `${label} · 仅刷新当前库存并保存当日快照`;
  if (state.status.demo_mode) {
    $("#noticeBar").textContent = "当前为独立演示数据库。填写项目根目录 wangdian_config.py 并重启服务后将自动切换到真实数据。";
    $("#noticeBar").classList.remove("hidden");
  } else if (!state.status.configured) {
    $("#noticeBar").textContent = "尚未配置旺店通接口凭证，数据同步暂不可用。";
    $("#noticeBar").classList.remove("hidden");
  } else {
    $("#noticeBar").classList.add("hidden");
  }
}

async function loadWarehouses() {
  const data = await api("/api/warehouses");
  const select = $("#warehouseSelect");
  state.warehouseData = data.items || [];
  state.warehouseCount = data.items.length;
  select.innerHTML = '<option value="">全部仓库</option>';
  data.items.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.warehouse_id;
    const name = item.warehouse_name || item.warehouse_no || `仓库 ${item.warehouse_id}`;
    option.textContent = `${name} · ${formatNumber(item.sku_count)} SKU`;
    select.appendChild(option);
  });
}

async function loadDashboard() {
  $("#tableLoading").classList.remove("hidden");
  $("#emptyState").classList.add("hidden");
  $("#inventoryBody").innerHTML = "";
  try {
    const data = await api(`/api/dashboard?${queryString()}`);
    state.data = data;
    renderSummary(data);
    renderDashboard(data);
    renderTable();
    $("#exportButton").href = `/api/export.csv?${exportQueryString()}`;
  } catch (error) {
    showToast(error.message);
    $("#resultCount").textContent = "数据读取失败";
  } finally {
    $("#tableLoading").classList.add("hidden");
  }
}

async function loadWarehouseSales() {
  $("#salesLoading").classList.remove("hidden");
  $("#salesEmptyState").classList.add("hidden");
  $("#salesBody").innerHTML = "";
  try {
    state.salesData = await api(`/api/warehouse-sales?${salesQueryString()}`);
    renderWarehouseSales();
  } catch (error) {
    showToast(error.message);
    $("#salesResultCount").textContent = "数据读取失败";
  } finally {
    $("#salesLoading").classList.add("hidden");
  }
}

async function loadShopSales() {
  $("#shopSalesLoading").classList.remove("hidden");
  $("#shopSalesEmptyState").classList.add("hidden");
  $("#shopSalesBody").innerHTML = "";
  try {
    state.shopSalesData = await api(`/api/shop-sales?${shopSalesQueryString()}`);
    renderShopSales();
  } catch (error) {
    showToast(error.message);
    $("#shopSalesResultCount").textContent = "数据读取失败";
  } finally {
    $("#shopSalesLoading").classList.add("hidden");
  }
}

async function loadInbound() {
  $("#inboundLoading").classList.remove("hidden");
  $("#inboundEmptyState").classList.add("hidden");
  $("#inboundBody").innerHTML = "";
  try {
    state.inboundData = await api(`/api/inbound?${inboundQueryString()}`);
    renderInbound();
  } catch (error) {
    showToast(error.message);
    $("#inboundResultCount").textContent = "数据读取失败";
  } finally {
    $("#inboundLoading").classList.add("hidden");
  }
}

async function loadShortNameSales() {
  $("#shortLoading").classList.remove("hidden");
  $("#shortEmptyState").classList.add("hidden");
  $("#shortNamesBody").innerHTML = "";
  try {
    state.shortData = await api(`/api/short-name-sales?${shortQueryString()}`);
    renderShortNameSales();
  } catch (error) {
    showToast(error.message);
    $("#shortResultCount").textContent = "数据读取失败";
  } finally {
    $("#shortLoading").classList.add("hidden");
  }
}

async function loadReplenishment() {
  $("#replenishmentLoading").classList.remove("hidden");
  $("#replenishmentEmptyState").classList.add("hidden");
  $("#replenishmentBody").innerHTML = "";
  try {
    state.replenishmentData = await api(`/api/replenishment?${replenishmentQueryString()}`);
    renderReplenishment();
  } catch (error) {
    showToast(error.message);
    $("#replenishmentResultCount").textContent = "数据读取失败";
  } finally {
    $("#replenishmentLoading").classList.add("hidden");
  }
}

async function loadPurchasePlan() {
  $("#purchasePlanLoading").classList.remove("hidden");
  $("#purchasePlanEmptyState").classList.add("hidden");
  $("#purchasePlanBody").innerHTML = "";
  try {
    state.purchasePlanData = await api(`/api/purchase-plan?${purchasePlanQueryString()}`);
    renderPurchasePlan();
  } catch (error) {
    showToast(error.message);
    $("#purchasePlanResultCount").textContent = "数据读取失败";
  } finally {
    $("#purchasePlanLoading").classList.add("hidden");
  }
}

async function loadTransferPlan() {
  $("#transferPlanLoading").classList.remove("hidden");
  $("#transferPlanEmptyState").classList.add("hidden");
  $("#transferPlanBody").innerHTML = "";
  try {
    state.transferPlanData = await api(`/api/transfer-plan?${transferPlanQueryString()}`);
    renderTransferPlan();
  } catch (error) {
    showToast(error.message);
    $("#transferPlanResultCount").textContent = "数据读取失败";
  } finally {
    $("#transferPlanLoading").classList.add("hidden");
  }
}

async function loadClearanceSummary() {
  $("#clearanceSummaryLoading").classList.remove("hidden");
  $("#clearanceSummaryEmptyState").classList.add("hidden");
  $("#clearanceSummaryBody").innerHTML = "";
  try {
    state.clearanceSummaryData = await api(`/api/clearance-summary?${clearanceSummaryQueryString()}`);
    renderClearanceSummary();
  } catch (error) {
    showToast(error.message);
    $("#clearanceSummaryResultCount").textContent = "数据读取失败";
  } finally {
    $("#clearanceSummaryLoading").classList.add("hidden");
  }
}

function renderClearanceSummary() {
  const data = state.clearanceSummaryData || {};
  const items = data.items || [];
  const summary = data.summary || {};
  const total = Number(data.pagination?.total || 0);
  const pages = Math.max(Math.ceil(total / state.clearanceSummaryPageSize), 1);
  const first = total ? (state.clearanceSummaryPage - 1) * state.clearanceSummaryPageSize + 1 : 0;
  const last = Math.min(state.clearanceSummaryPage * state.clearanceSummaryPageSize, total);
  const updated = summary.updated_at || "--";
  const weekly = data.latest_weekly_snapshot;
  $("#clearanceSummaryResultCount").textContent = `共 ${formatNumber(total)} 个仓库-SKU · 当前 ${formatNumber(first)}-${formatNumber(last)}`;
  $("#clearanceSummaryUpdated").textContent = `最近库存更新 ${updated === "--" ? "--" : updated.replace("T", " ")}${weekly ? ` · 最近周快照 ${weekly.snapshot_date}` : " · 尚无周快照"}`;
  $("#clearanceSummaryPageInfo").textContent = `第 ${state.clearanceSummaryPage} / ${pages} 页`;
  $("#clearanceSummaryPreviousPage").disabled = state.clearanceSummaryPage <= 1;
  $("#clearanceSummaryNextPage").disabled = state.clearanceSummaryPage >= pages;
  $("#clearanceSummarySkuCount").textContent = formatNumber(summary.sku_count);
  $("#clearanceSummaryWarehouseCount").textContent = formatNumber(summary.warehouse_count);
  $("#clearanceSummaryStockQty").textContent = formatNumber(summary.stock_num);
  $("#clearanceSummaryAvailableQty").textContent = formatNumber(summary.available_num);
  $("#clearanceSummaryPurchaseCost").textContent = formatClearanceCurrency(summary.purchase_cost);
  $("#clearanceSummaryMissingPurchasePrice").textContent = formatNumber(summary.missing_purchase_price_count);
  $("#clearanceSummaryEmptyState").classList.toggle("hidden", items.length > 0);
  $("#clearanceSummaryBody").innerHTML = items.map((item) => `
    <tr data-sku="${escapeHtml(item.sku_no)}">
      <td class="warehouse-cell"><strong>${escapeHtml(item.warehouse_name || item.warehouse_no || `仓库 ${item.warehouse_id}`)}</strong></td>
      <td class="product-cell"><strong>${escapeHtml(item.short_name || item.goods_name || "未命名货品")}</strong><span>${escapeHtml([item.goods_name, item.spec_name].filter(Boolean).join(" · ") || item.goods_no || "-")}</span></td>
      <td><span class="sku-code">${escapeHtml(item.sku_no)}</span></td>
      <td>${escapeHtml(item.supplier_name || "供应商待补充")}</td>
      <td class="numeric">${formatNumber(item.stock_num)}</td>
      <td class="numeric">${formatNumber(item.available_num)}</td>
      <td class="numeric">${Number(item.purchase_price) > 0 ? formatClearanceCurrency(item.purchase_price) : "未配置"}</td>
      <td class="numeric net-value">${Number(item.purchase_price) > 0 ? formatClearanceCurrency(item.purchase_cost) : "--"}</td>
      <td class="modified-cell">${escapeHtml((item.synced_at || "--").replace("T", " "))}</td>
    </tr>`).join("");
  $("#clearanceSummaryBody").querySelectorAll("tr").forEach((row) => row.addEventListener("click", () => openSku(row.dataset.sku)));
}

function renderWarehouseSales() {
  const data = state.salesData;
  const items = data.items || [];
  const total = Number(data.pagination.total || 0);
  const pages = Math.max(Math.ceil(total / state.salesPageSize), 1);
  const first = total ? (state.salesPage - 1) * state.salesPageSize + 1 : 0;
  const last = Math.min(state.salesPage * state.salesPageSize, total);
  $("#salesResultCount").textContent = `共 ${formatNumber(total)} 个仓库-SKU · 当前 ${formatNumber(first)}-${formatNumber(last)}`;
  $("#salesPageInfo").textContent = `第 ${state.salesPage} / ${pages} 页`;
  $("#salesPreviousPage").disabled = state.salesPage <= 1;
  $("#salesNextPage").disabled = state.salesPage >= pages;
  $("#salesTotalQty").textContent = formatNumber(data.summary.sales_qty);
  $("#sales7dQty").textContent = formatNumber(data.summary.sales_7d_qty);
  $("#sales15dQty").textContent = formatNumber(data.summary.sales_15d_qty);
  $("#sales30dQty").textContent = formatNumber(data.summary.sales_30d_qty);
  $("#salesReturnQty").textContent = formatNumber(data.summary.return_qty);
  $("#salesNetQty").textContent = formatNumber(data.summary.net_sales_qty);
  $("#salesWarehouseCount").textContent = formatNumber(data.summary.warehouse_count);
  $("#salesEmptyState").classList.toggle("hidden", items.length > 0);
  $("#salesBody").innerHTML = items.map((item) => `
    <tr data-sku="${escapeHtml(item.sku_no)}">
      <td class="warehouse-cell"><strong>${escapeHtml(item.warehouse_name || item.warehouse_no || `仓库 ${item.warehouse_id}`)}</strong></td>
      <td class="sticky-sales-sku"><span class="sku-code">${escapeHtml(item.sku_no)}</span></td>
      <td class="product-cell"><strong>${escapeHtml(item.short_name || item.goods_name || "未命名货品")}</strong><span>${escapeHtml([item.goods_name, item.spec_name].filter(Boolean).join(" · ") || item.goods_no || "-")}</span></td>
      <td class="numeric net-value">${formatNumber(item.sales_qty)}</td>
      <td class="numeric return-value">${item.return_qty ? formatNumber(item.return_qty) : "-"}</td>
      <td class="numeric"><strong>${formatNumber(item.net_sales_qty)}</strong></td>
      <td class="numeric">${formatNumber(item.sales_7d_qty)}</td>
      <td class="numeric">${formatNumber(item.sales_15d_qty)}</td>
      <td class="numeric">${formatNumber(item.sales_30d_qty)}</td>
      <td class="numeric">${formatNumber(item.stock_num)}</td>
      <td class="numeric">${formatNumber(item.available_num)}</td>
      <td class="numeric">${formatNumber(item.purchase_in_transit_num)}</td>
      <td class="numeric">${item.trend_coefficient === null || item.trend_coefficient === undefined ? "-" : formatCalculationNumber(item.trend_coefficient)}</td>
      <td class="numeric">${formatDays(item.inventory_with_transit_days)}</td>
      <td>${escapeHtml(formatDateValue(item.estimated_stockout_date_with_transit))}</td>
    </tr>
  `).join("");
  $("#salesBody").querySelectorAll("tr").forEach((row) => row.addEventListener("click", () => openSku(row.dataset.sku)));
  refreshIcons();
}

function renderShopSales() {
  const data = state.shopSalesData || {};
  const items = data.items || [];
  const total = Number(data.pagination?.total || 0);
  const pages = Math.max(Math.ceil(total / state.shopSalesPageSize), 1);
  const first = total ? (state.shopSalesPage - 1) * state.shopSalesPageSize + 1 : 0;
  const last = Math.min(state.shopSalesPage * state.shopSalesPageSize, total);
  const summary = data.summary || {};
  $("#shopSalesResultCount").textContent = `共 ${formatNumber(total)} 个店铺-SKU · 当前 ${formatNumber(first)}-${formatNumber(last)}`;
  $("#shopSalesPageInfo").textContent = `第 ${state.shopSalesPage} / ${pages} 页`;
  $("#shopSalesPreviousPage").disabled = state.shopSalesPage <= 1;
  $("#shopSalesNextPage").disabled = state.shopSalesPage >= pages;
  $("#shopSalesShopCount").textContent = formatNumber(summary.shop_count);
  $("#shopSalesSkuCount").textContent = formatNumber(summary.sku_count);
  $("#shopSalesTotalQty").textContent = formatNumber(summary.sales_qty);
  $("#shopSalesReturnQty").textContent = formatNumber(summary.return_qty);
  $("#shopSalesNetQty").textContent = formatNumber(summary.net_sales_qty);
  $("#shopSalesAmount").textContent = formatCurrency(summary.sales_amount);
  const select = $("#shopSalesShopSelect");
  const selected = select.value;
  select.innerHTML = '<option value="">全部店铺</option>' + (data.shops || []).map((shop) =>
    `<option value="${escapeHtml(shop.shop_no || "")}">${escapeHtml(shop.shop_name || "未识别店铺")} · ${escapeHtml(shop.shop_no || "未编码")}</option>`
  ).join("");
  if ([...select.options].some((option) => option.value === selected)) select.value = selected;
  $("#shopSalesEmptyState").classList.toggle("hidden", items.length > 0);
  $("#shopSalesBody").innerHTML = items.map((item) => `
    <tr data-sku="${escapeHtml(item.sku_no)}">
      <td class="warehouse-cell"><strong>${escapeHtml(item.shop_name || "未识别店铺")}</strong></td>
      <td><span class="sku-code">${escapeHtml(item.shop_no || "未编码")}</span></td>
      <td class="product-cell"><strong>${escapeHtml(item.short_name || item.goods_name || "未命名货品")}</strong><span>${escapeHtml([item.goods_name, item.spec_name].filter(Boolean).join(" · ") || item.goods_no || "-")}</span></td>
      <td><span class="sku-code">${escapeHtml(item.sku_no)}</span></td>
      <td class="numeric net-value">${formatNumber(item.sales_qty)}</td>
      <td class="numeric return-value">${item.return_qty ? formatNumber(item.return_qty) : "-"}</td>
      <td class="numeric"><strong>${formatNumber(item.net_sales_qty)}</strong></td>
      <td class="numeric">${formatCurrency(item.sales_amount)}</td>
      <td>${escapeHtml(item.warehouse_id || "-")}</td>
    </tr>`).join("");
  $("#shopSalesBody").querySelectorAll("tr").forEach((row) => row.addEventListener("click", () => openSku(row.dataset.sku, $("#shopSalesStartDate").value, $("#shopSalesEndDate").value)));
  refreshIcons();
}

function renderInbound() {
  const data = state.inboundData;
  const items = data.items || [];
  const total = Number(data.pagination.total || 0);
  const pages = Math.max(Math.ceil(total / state.inboundPageSize), 1);
  const first = total ? (state.inboundPage - 1) * state.inboundPageSize + 1 : 0;
  const last = Math.min(state.inboundPage * state.inboundPageSize, total);
  $("#inboundResultCount").textContent = `共 ${formatNumber(total)} 个仓库-SKU · 当前 ${formatNumber(first)}-${formatNumber(last)}`;
  $("#inboundPageInfo").textContent = `第 ${state.inboundPage} / ${pages} 页`;
  $("#inboundPreviousPage").disabled = state.inboundPage <= 1;
  $("#inboundNextPage").disabled = state.inboundPage >= pages;
  $("#inboundTotalQty").textContent = formatNumber(data.summary.inbound_qty);
  $("#inboundPurchaseQty").textContent = formatNumber(data.summary.purchase_qty);
  $("#inboundReturnQty").textContent = formatNumber(data.summary.return_qty);
  $("#inboundTransferQty").textContent = formatNumber(data.summary.transfer_qty);
  $("#inboundOtherQty").textContent = formatNumber(data.summary.other_qty);
  $("#inboundSkuCount").textContent = formatNumber(data.summary.sku_count);
  $("#inboundEmptyState").classList.toggle("hidden", items.length > 0);
  $("#inboundDaily").innerHTML = (data.daily || []).map((day) => `
    <div class="inbound-day">
      <span>${escapeHtml(day.date.slice(5))}</span>
      <strong>${formatNumber(day.inbound_qty)}</strong>
      <small>采购 ${formatNumber(day.purchase_qty)} · 退货 ${formatNumber(day.return_qty)} · 调拨 ${formatNumber(day.transfer_qty)}</small>
    </div>
  `).join("");
  $("#inboundBody").innerHTML = items.map((item) => `
    <tr data-sku="${escapeHtml(item.sku_no)}">
      <td class="warehouse-cell"><strong>${escapeHtml(item.warehouse_name || item.warehouse_no || `仓库 ${item.warehouse_id}`)}</strong></td>
      <td><span class="sku-code">${escapeHtml(item.sku_no)}</span></td>
      <td class="product-cell"><strong>${escapeHtml(item.short_name || item.goods_name || "未命名货品")}</strong><span>${escapeHtml([item.goods_name, item.spec_name].filter(Boolean).join(" · ") || item.goods_no || "-")}</span></td>
      <td class="numeric inbound-value">${formatNumber(item.inbound_qty)}</td>
      <td class="numeric">${item.purchase_qty ? formatNumber(item.purchase_qty) : "-"}</td>
      <td class="numeric return-value">${item.return_qty ? formatNumber(item.return_qty) : "-"}</td>
      <td class="numeric">${item.transfer_qty ? formatNumber(item.transfer_qty) : "-"}</td>
      <td class="numeric">${item.other_qty ? formatNumber(item.other_qty) : "-"}</td>
      <td class="numeric">${formatNumber(item.order_count)}</td>
      <td class="source-order-cell" title="${escapeHtml(item.return_source_order_nos || "")}">${escapeHtml(item.return_source_order_nos || "-")}</td>
      <td class="modified-cell">${escapeHtml((item.last_inbound_time || "-").slice(0, 16))}</td>
    </tr>
  `).join("");
  $("#inboundBody").querySelectorAll("tr").forEach((row) => row.addEventListener("click", () => openSku(
    row.dataset.sku, $("#inboundStartDate").value, $("#inboundEndDate").value
  )));
  refreshIcons();
}

function renderShortNameSales() {
  const data = state.shortData;
  const items = data.items || [];
  const total = Number(data.pagination.total || 0);
  const pages = Math.max(Math.ceil(total / state.shortPageSize), 1);
  const first = total ? (state.shortPage - 1) * state.shortPageSize + 1 : 0;
  const last = Math.min(state.shortPage * state.shortPageSize, total);
  $("#shortResultCount").textContent = `共 ${formatNumber(total)} 个简称 · 当前 ${formatNumber(first)}-${formatNumber(last)}`;
  $("#shortPageInfo").textContent = `第 ${state.shortPage} / ${pages} 页`;
  $("#shortPreviousPage").disabled = state.shortPage <= 1;
  $("#shortNextPage").disabled = state.shortPage >= pages;
  $("#shortSalesQty").textContent = formatNumber(data.summary.sales_qty);
  $("#shortReturnQty").textContent = formatNumber(data.summary.return_qty);
  $("#shortNetQty").textContent = formatNumber(data.summary.net_sales_qty);
  $("#shortNameCount").textContent = formatNumber(total);
  $("#shortEmptyState").classList.toggle("hidden", items.length > 0);
  $("#shortNamesBody").innerHTML = items.map((item) => {
    const warehouseText = item.warehouses.length
      ? item.warehouses.map((warehouse) => `<span><strong>${escapeHtml(warehouse.warehouse_name || `仓库 ${warehouse.warehouse_id}`)}</strong> ${formatNumber(warehouse.sales_qty)}</span>`).join("")
      : '<span class="muted">无发货</span>';
    return `<tr>
      <td class="short-name-cell"><strong>${escapeHtml(item.display_name)}</strong>${item.is_fallback ? '<span>简称待补</span>' : ''}</td>
      <td class="product-list-cell">${escapeHtml(item.goods_names || "未命名货品")}</td>
      <td class="numeric">${formatNumber(item.sku_count)}</td>
      <td class="numeric net-value">${formatNumber(item.sales_qty)}</td>
      <td class="numeric return-value">${item.return_qty ? formatNumber(item.return_qty) : "-"}</td>
      <td class="numeric"><strong>${formatNumber(item.net_sales_qty)}</strong></td>
      <td class="numeric">${formatNumber(item.stock_num)}</td>
      <td><div class="warehouse-breakdown">${warehouseText}</div></td>
    </tr>`;
  }).join("");
}

function renderReplenishment() {
  const data = state.replenishmentData;
  const items = data.items || [];
  const total = Number(data.pagination.total || 0);
  const pages = Math.max(Math.ceil(total / state.replenishmentPageSize), 1);
  const first = total ? (state.replenishmentPage - 1) * state.replenishmentPageSize + 1 : 0;
  const last = Math.min(state.replenishmentPage * state.replenishmentPageSize, total);
  $("#replenishmentResultCount").textContent = `共 ${formatNumber(total)} 个仓库-SKU 预警 · 当前 ${formatNumber(first)}-${formatNumber(last)}`;
  const modeLabel = data.alert_mode === "clearance" ? "当前模式：清仓预警" : "当前模式：正常预警（堆积）";
  $("#replenishmentRange").textContent = `${modeLabel} · 非清仓：含采购在途预测库存超过 ${formatNumber(data.inventory_alert_threshold_days || 90)} 天 · 清仓：${data.clearance_alert_rule || "--"} · 7日 ${data.range.start} 至 ${data.range.end} · 库存快照 ${data.snapshot_date || "--"}`;
  $("#replenishmentPageInfo").textContent = `第 ${state.replenishmentPage} / ${pages} 页`;
  $("#replenishmentPreviousPage").disabled = state.replenishmentPage <= 1;
  $("#replenishmentNextPage").disabled = state.replenishmentPage >= pages;
  $("#replenishCount").textContent = formatNumber(data.summary.critical_count);
  $("#stockoutCount").textContent = formatNumber(data.summary.warning_count);
  $("#stagnantCount").textContent = formatNumber(data.summary.attention_count);
  $("#clearanceAlertCount").textContent = formatNumber(data.summary.clearance_alert_count);
  $("#replenishmentEmptyState").classList.toggle("hidden", items.length > 0);
  $("#replenishmentBody").innerHTML = items.map((item) => {
    const coverage = item.forecast_coverage_days == null ? "--" : `${formatNumber(item.forecast_coverage_days)} 天`;
    const projected = item.projected_coverage_days == null ? "--" : `${formatNumber(item.projected_coverage_days)} 天`;
    const badgeClass = ({ "严重积压": "decision-danger", "中度积压": "decision-warning", "库存预警": "decision-normal", "清仓预警": "decision-clearance" })[item.recommendation] || "decision-normal";
    return `<tr data-sku="${escapeHtml(item.sku_no)}">
      <td class="warehouse-cell"><strong>${escapeHtml(item.warehouse_name || item.warehouse_no || `仓库 ${item.warehouse_id}`)}</strong></td>
      <td class="product-cell"><strong>${escapeHtml(item.short_name || item.goods_name || "未命名货品")}</strong><span>${escapeHtml([item.goods_name, item.spec_name].filter(Boolean).join(" · ") || item.goods_no || "-")}</span><small class="metadata-status ${item.metadata_status === "已配置" ? "metadata-ready" : "metadata-pending"}">${escapeHtml(item.metadata_status || "待补充")}</small></td>
      <td><span class="sku-code">${escapeHtml(item.sku_no)}</span></td>
      <td class="numeric">${formatNumber(item.available_num)}</td>
      <td class="numeric">${formatNumber(item.purchase_in_transit_num)}</td>
      <td class="numeric net-value">${formatNumber(item.sales_7d_qty)}</td>
      <td class="numeric">${formatNumber(item.sales_15d_qty)}</td>
      <td class="numeric">${formatNumber(item.sales_30d_qty)}</td>
      <td class="numeric"><strong>${item.trend_coefficient == null ? "--" : formatNumber(item.trend_coefficient)}</strong><span class="muted trend-label">${escapeHtml(item.trend_status || "")}</span></td>
      <td class="numeric">${formatNumber(item.forecast_daily_sales)}</td>
      <td class="numeric">${coverage}</td>
      <td class="numeric">${projected}</td>
      <td><span class="decision-badge ${badgeClass}" title="${escapeHtml(item.trend_action || "")}">${escapeHtml(item.recommendation)}</span></td>
    </tr>`;
  }).join("");
  $("#replenishmentBody").querySelectorAll("tr").forEach((row) => row.addEventListener("click", () => openSku(row.dataset.sku)));
}

function renderPurchasePlan() {
  const data = state.purchasePlanData;
  const items = data.items || [];
  const total = Number(data.pagination.total || 0);
  const pages = Math.max(Math.ceil(total / state.purchasePlanPageSize), 1);
  const first = total ? (state.purchasePlanPage - 1) * state.purchasePlanPageSize + 1 : 0;
  const last = Math.min(state.purchasePlanPage * state.purchasePlanPageSize, total);
  $("#purchasePlanResultCount").textContent = `共 ${formatNumber(total)} 个五仓启用 SKU · 当前 ${formatNumber(first)}-${formatNumber(last)}`;
  $("#purchasePlanRange").textContent = `统计 ${data.range.start} 至 ${data.range.end} · ${data.planning_basis || ""}`;
  $("#purchasePlanPageInfo").textContent = `第 ${state.purchasePlanPage} / ${pages} 页`;
  $("#purchasePlanPreviousPage").disabled = state.purchasePlanPage <= 1;
  $("#purchasePlanNextPage").disabled = state.purchasePlanPage >= pages;
  $("#purchasePlanRiskCount").textContent = formatNumber(data.summary.severe_shortage_count);
  $("#purchasePlanWeekCount").textContent = formatNumber(data.summary.due_within_week_count);
  $("#purchasePlanPlannedCount").textContent = formatNumber(data.summary.future_purchase_count);
  $("#purchasePlanLowDemandCount").textContent = formatNumber(data.summary.low_demand_count);
  $("#purchasePlanCalculatedQty").textContent = formatNumber(data.summary.total_calculated_order_qty);
  $("#purchasePlanMoqUpliftQty").textContent = formatNumber(data.summary.total_moq_uplift_qty);
  $("#purchasePlanQty").textContent = formatNumber(data.summary.total_order_qty);
  $("#purchasePlanEmptyState").classList.toggle("hidden", items.length > 0);
  $("#purchasePlanBody").innerHTML = items.map((item) => {
    const statusClass = "decision-normal";
    const lead = item.lead_days == null ? "--" : `${formatNumber(item.advance_days)} / ${formatNumber(item.buffer_days)}`;
    return `<tr data-sku="${escapeHtml(item.sku_no)}">
      <td><span class="decision-badge ${statusClass}" title="${escapeHtml(item.plan_reason || "")}">${escapeHtml(item.timing_label || "")}</span></td>
      <td><strong>${escapeHtml(item.suggested_order_date || "--")}</strong><small class="muted">${escapeHtml(item.order_window || "")}${item.estimated_arrival_date ? ` · 本批到货 ${item.estimated_arrival_date}` : ""}${item.next_scheduled_arrival_date ? ` · 下批到货 ${item.next_scheduled_arrival_date}` : ""}</small></td>
      <td>${escapeHtml(item.warehouse_name || item.warehouse_no || `仓库 ${item.warehouse_id}`)}</td>
      <td class="product-cell"><strong>${escapeHtml(item.short_name || item.goods_name || "未命名货品")}</strong><span>${escapeHtml([item.goods_name, item.spec_name].filter(Boolean).join(" · ") || item.sku_no)}</span></td>
      <td>${escapeHtml(item.supplier_name || "供应商待补充")}</td>
      <td>${escapeHtml(item.product_structure || "结构待补充")}</td>
      <td>${escapeHtml(item.production_line || "--")}</td>
      <td>${escapeHtml(item.production_capacity || "--")}</td>
      <td class="numeric">${formatNumber(item.production_days)}</td>
      <td class="numeric">${lead}</td>
      <td class="numeric">${formatNumber(item.available_num)}</td>
      <td class="numeric">${formatNumber(item.purchase_in_transit_num)}</td>
      <td class="numeric">${formatNumber(item.transfer_qty)}</td>
      <td class="numeric"><strong>${item.trend_coefficient == null ? "--" : formatCalculationNumber(item.trend_coefficient)}</strong><small class="trend-label muted">${escapeHtml(item.trend_status || "")}</small></td>
      <td class="numeric">${formatCalculationNumber(item.daily_sales)}<small class="trend-label muted">${escapeHtml(item.forecast_basis || "")}</small></td>
      <td>${escapeHtml(item.estimated_stockout_date || "--")}</td>
      <td class="numeric">${item.moq ? formatNumber(item.moq) : "按计算"}</td>
      <td class="numeric">${formatCalculationNumber(item.calculated_order_qty)}</td>
      <td class="numeric"><strong>${formatNumber(item.final_order_qty)}</strong>${item.moq_uplift_qty > 0 ? `<small class="trend-label muted">MOQ 补足 +${formatNumber(item.moq_uplift_qty)}</small>` : ""}</td>
    </tr>`;
  }).join("");
  $("#purchasePlanBody").querySelectorAll("tr").forEach((row) => row.addEventListener("click", () => openSku(row.dataset.sku)));
}

function renderTransferPlan() {
  const data = state.transferPlanData;
  const items = data.items || [];
  const total = Number(data.pagination.total || 0);
  const pages = Math.max(Math.ceil(total / state.transferPlanPageSize), 1);
  const first = total ? (state.transferPlanPage - 1) * state.transferPlanPageSize + 1 : 0;
  const last = Math.min(state.transferPlanPage * state.transferPlanPageSize, total);
  const summary = data.summary || {};
  $("#transferPlanResultCount").textContent = `共 ${formatNumber(total)} 条仓间调拨建议 · 当前 ${formatNumber(first)}-${formatNumber(last)}`;
  $("#transferPlanRange").textContent = `统计 ${data.range.start} 至 ${data.range.end} · ${data.planning_basis || ""}`;
  $("#transferPlanPageInfo").textContent = `第 ${state.transferPlanPage} / ${pages} 页`;
  $("#transferPlanPreviousPage").disabled = state.transferPlanPage <= 1;
  $("#transferPlanNextPage").disabled = state.transferPlanPage >= pages;
  $("#transferPlanQty").textContent = formatNumber(summary.transfer_qty);
  $("#transferPlanSkuCount").textContent = formatNumber(summary.sku_count);
  $("#transferPlanWarehouseCount").textContent = formatNumber(summary.target_warehouse_count);
  $("#transferPlanEmptyState").classList.toggle("hidden", items.length > 0);
  $("#transferPlanBody").innerHTML = items.map((item) => {
    return `<tr data-sku="${escapeHtml(item.sku_no)}">
      <td>${escapeHtml(item.source_warehouse_name || `仓库 ${item.source_warehouse_id}`)}</td>
      <td>${escapeHtml(item.target_warehouse_name || `仓库 ${item.target_warehouse_id}`)}</td>
      <td class="product-cell"><strong>${escapeHtml(item.short_name || item.goods_name || "未命名货品")}</strong><span>${escapeHtml([item.goods_name, item.spec_name].filter(Boolean).join(" · ") || item.sku_no)}</span></td>
      <td><span class="sku-code">${escapeHtml(item.sku_no)}</span></td>
      <td class="numeric"><strong>${formatNumber(item.transfer_qty)}</strong></td>
      <td class="numeric">${formatNumber(item.target_daily_sales)}</td>
      <td>${escapeHtml(item.target_stockout_date || "--")}</td>
    </tr>`;
  }).join("");
  $("#transferPlanBody").querySelectorAll("tr").forEach((row) => row.addEventListener("click", () => openSku(row.dataset.sku)));
}

function reloadActiveView() {
  if (state.activeView === "dashboard") return loadDashboard();
  if (state.activeView === "inbound") return loadInbound();
  if (state.activeView === "sales") return loadWarehouseSales();
  if (state.activeView === "shopSales") return loadShopSales();
  if (state.activeView === "shortNames") return loadShortNameSales();
  if (state.activeView === "replenishment") return loadReplenishment();
  if (state.activeView === "purchasePlan") return loadPurchasePlan();
  if (state.activeView === "transferPlan") return loadTransferPlan();
  if (state.activeView === "clearanceSummary") return loadClearanceSummary();
  return loadDashboard();
}

function renderSummary(data) {
  const s = data.summary;
  const availableRate = Number(s.stock_num) > 0 ? Number(s.available_num) / Number(s.stock_num) * 100 : 0;
  const shippedQty = Number(s.movement_sales_qty || s.sales_qty || 0);
  const returnedQty = Number(s.movement_return_qty || s.return_qty || 0);
  const netShippedQty = shippedQty - returnedQty;
  const returnRate = shippedQty > 0 ? returnedQty / shippedQty * 100 : 0;
  $("#metricStock").textContent = formatNumber(s.stock_num);
  $("#metricSnapshot").textContent = `快照 ${data.snapshot_date || "--"}`;
  $("#metricAvailable").textContent = formatNumber(s.available_num);
  $("#metricTransit").textContent = formatNumber(s.purchase_in_transit_num);
  $("#metricStockRate").textContent = `可用率 ${availableRate.toFixed(1)}%`;
  $("#metricStockValue").textContent = formatNumber(s.sku_count);
  $("#metricSales").textContent = formatNumber(shippedQty);
  $("#metricSalesPeriod").textContent = `${data.range.days} 天发货量`;
  $("#metricNetSales").textContent = formatNumber(netShippedQty);
  $("#metricReturnRate").textContent = `退货率 ${returnRate.toFixed(1)}%`;
  $("#metricReturn").textContent = formatNumber(returnedQty);
  $("#metricReturnPeriod").textContent = `${data.range.days} 天退货入库`;
  $("#metricPurchase").textContent = formatNumber(s.purchase_qty);
  $("#metricUnavailable").textContent = formatNumber(s.unavailable_sku_count);
  $("#metricRiskNote").textContent = `负库存 ${formatNumber(s.negative_sku_count)} · 零库存 ${formatNumber(s.zero_sku_count)}`;
}

function renderRanking(items) {
  const list = $("#topSkuList");
  list.innerHTML = items.slice().sort((a, b) => Number(b.stock_num) - Number(a.stock_num)).slice(0, 5).map((item, index) => `
    <li data-sku="${escapeHtml(item.sku_no)}">
      <span class="rank-no">${String(index + 1).padStart(2, "0")}</span>
      <span class="rank-name"><strong>${escapeHtml(item.short_name || item.goods_name || "未命名货品")}</strong><span>${escapeHtml(item.sku_no)}</span></span>
      <span class="rank-value">${formatNumber(item.stock_num)}</span>
    </li>
  `).join("");
  list.querySelectorAll("li").forEach((row) => row.addEventListener("click", () => openSku(row.dataset.sku)));
}

function renderDashboard(data) {
  const summary = data.summary || {};
  $("#dashboardRange").textContent = `经营数据 ${data.range.start} 至 ${data.range.end} · ${data.range.days} 天 · 库存快照 ${data.snapshot_date || "--"}`;
  renderRanking(data.items || []);
  drawChart(data.daily || []);
  renderWarehouseOverview();

  const total = Math.max(Number(summary.sku_count || 0), 1);
  const unavailable = Number(summary.unavailable_sku_count || 0);
  const negative = Number(summary.negative_sku_count || 0);
  const zero = Number(summary.zero_sku_count || 0);
  const health = [
    { label: "可用库存", value: Math.max(total - unavailable, 0), kind: "" },
    { label: "其他无可用", value: Math.max(unavailable - zero - negative, 0), kind: "warning" },
    { label: "零库存", value: zero, kind: "warning" },
    { label: "负库存", value: negative, kind: "danger" },
  ];
  $("#inventoryHealth").innerHTML = health.map((item) => `
    <div class="health-row ${item.kind}">
      <span>${item.label}</span><div class="health-bar"><i style="width:${Math.min(item.value / total * 100, 100)}%"></i></div><strong>${formatNumber(item.value)}</strong>
    </div>`).join("");
}

function renderWarehouseOverview() {
  const selected = $("#warehouseSelect").value;
  const rows = state.warehouseData
    .filter((row) => !selected || row.warehouse_id === selected)
    .sort((left, right) => Number(right.stock_num) - Number(left.stock_num));
  const maxStock = Math.max(...rows.map((row) => Math.max(Number(row.stock_num || 0), 0)), 1);
  $("#warehouseOverviewCount").textContent = `共 ${formatNumber(rows.length)} 个仓库`;
  $("#warehouseOverview").innerHTML = rows.slice(0, 8).map((row) => {
    const stock = Number(row.stock_num || 0);
    const available = Number(row.available_num || 0);
    const transit = Number(row.purchase_in_transit_num || 0);
    const width = Math.max(Math.min(Math.max(stock, 0) / maxStock * 100, 100), 0);
    const name = row.warehouse_name || row.warehouse_no || `仓库 ${row.warehouse_id}`;
    return `<div class="warehouse-overview-row">
      <div class="warehouse-overview-name"><strong>${escapeHtml(name)}</strong><span>${formatNumber(row.sku_count)} 个 SKU</span></div>
      <div class="warehouse-stock-bar"><i style="width:${width}%"></i></div>
      <div class="warehouse-overview-value">${formatNumber(stock)}<small>库存</small></div>
      <div class="warehouse-overview-value">${formatNumber(available)}<small>可用 · 在途 ${formatNumber(transit)}</small></div>
    </div>`;
  }).join("") || '<div class="muted">当前筛选条件下没有仓库库存</div>';
}

function moveFilterToolbar(view) {
  const slots = {
    dashboard: "dashboardToolbarSlot",
    inventory: "inventoryToolbarSlot",
    inbound: "inboundToolbarSlot",
    sales: "salesToolbarSlot",
    shopSales: "shopSalesToolbarSlot",
    shortNames: "shortNamesToolbarSlot",
    replenishment: "replenishmentToolbarSlot",
    purchasePlan: "purchasePlanToolbarSlot",
    transferPlan: "transferPlanToolbarSlot",
    clearanceSummary: "clearanceSummaryToolbarSlot",
  };
  const slot = $(`#${slots[view]}`);
  const toolbar = $(".filter-band");
  if (slot && toolbar.parentElement !== slot) slot.appendChild(toolbar);
}

function sortedItems() {
  if (!state.data) return [];
  const { key, direction } = state.sort;
  const factor = direction === "asc" ? 1 : -1;
  return state.data.items.slice().sort((a, b) => {
    const left = a[key];
    const right = b[key];
    if (left == null) return 1;
    if (right == null) return -1;
    if (typeof left === "number" && typeof right === "number") return (left - right) * factor;
    return String(left).localeCompare(String(right), "zh-CN") * factor;
  });
}

function renderTable() {
  const items = sortedItems();
  const body = $("#inventoryBody");
  const total = Number(state.data.pagination.total || 0);
  const pages = Math.max(Math.ceil(total / state.pageSize), 1);
  const first = total ? (state.page - 1) * state.pageSize + 1 : 0;
  const last = Math.min(state.page * state.pageSize, total);
  $("#resultCount").textContent = `共 ${formatNumber(total)} 个 SKU · 当前 ${formatNumber(first)}-${formatNumber(last)}`;
  $("#pageInfo").textContent = `第 ${state.page} / ${pages} 页`;
  $("#previousPage").disabled = state.page <= 1;
  $("#nextPage").disabled = state.page >= pages;
  $("#emptyState").classList.toggle("hidden", items.length > 0);
  body.innerHTML = items.map((item) => {
    const stock = Number(item.stock_num || 0);
    const available = Number(item.available_num || 0);
    const status = stock < 0 ? "负库存" : available <= 0 ? "无可用" : stock === 0 ? "零库存" : "正常";
    const statusClass = stock < 0 ? "stock-negative" : available <= 0 ? "stock-unavailable" : "stock-normal";
    return `
      <tr data-sku="${escapeHtml(item.sku_no)}">
        <td class="sticky-col"><span class="sku-code">${escapeHtml(item.sku_no)}</span></td>
      <td class="product-cell"><strong>${escapeHtml(item.short_name || item.goods_name || "未命名货品")}</strong><span>${escapeHtml([item.goods_name, item.spec_name].filter(Boolean).join(" · ") || item.goods_no || "-")}</span></td>
        <td class="numeric">${formatNumber(item.stock_num)}</td>
        <td class="numeric">${formatNumber(item.available_num)}</td>
        <td class="numeric">${formatNumber(item.purchase_in_transit_num)}</td>
        <td class="numeric">${formatNumber(item.warehouse_count)}</td>
        <td class="modified-cell">${escapeHtml((item.modified || "-").slice(0, 16))}</td>
        <td><span class="stock-status ${statusClass}">${status}</span></td>
        <td class="action-cell"><i class="row-arrow" data-lucide="chevron-right"></i></td>
      </tr>`;
  }).join("");
  body.querySelectorAll("tr").forEach((row) => row.addEventListener("click", () => openSku(row.dataset.sku)));
  refreshIcons();
}

function drawChart(daily) {
  const canvas = $("#trendChart");
  const wrap = canvas.parentElement;
  const ratio = window.devicePixelRatio || 1;
  const width = wrap.clientWidth;
  const height = wrap.clientHeight;
  canvas.width = Math.max(width * ratio, 1);
  canvas.height = Math.max(height * ratio, 1);
  const ctx = canvas.getContext("2d");
  ctx.scale(ratio, ratio);
  ctx.clearRect(0, 0, width, height);
  state.chartPoints = [];
  const chartDaily = daily.map((row) => ({
    ...row,
    sales_qty: Number(row.movement_sales_qty || row.sales_qty || 0),
    return_qty: Number(row.movement_return_qty || row.return_qty || 0),
  }));
  if (!chartDaily.length || width < 20) return;
  const pad = { left: 37, right: 10, top: 10, bottom: 25 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const max = Math.max(...chartDaily.map((d) => Number(d.sales_qty || 0)), 1) * 1.15;
  ctx.font = '10px "IBM Plex Mono", monospace';
  ctx.textAlign = "right";
  ctx.fillStyle = "#85918c";
  ctx.strokeStyle = "#e6ebe8";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = pad.top + plotH * i / 4;
    const value = Math.round(max * (1 - i / 4));
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(width - pad.right, y); ctx.stroke();
    ctx.fillText(String(value), pad.left - 7, y + 3);
  }
  const step = plotW / chartDaily.length;
  const barW = Math.max(2, Math.min(9, step * .42));
  const points = [];
  chartDaily.forEach((d, i) => {
    const x = pad.left + step * (i + .5);
    const salesH = Number(d.sales_qty || 0) / max * plotH;
    const returnH = Number(d.return_qty || 0) / max * plotH;
    const net = Number(d.sales_qty || 0) - Number(d.return_qty || 0);
    const y = pad.top + plotH - net / max * plotH;
    ctx.fillStyle = "#77a994";
    ctx.fillRect(x - barW - 1, pad.top + plotH - salesH, barW, salesH);
    ctx.fillStyle = "#db8888";
    ctx.fillRect(x + 1, pad.top + plotH - returnH, barW, returnH);
    points.push({ x, y, data: d, net });
  });
  ctx.beginPath();
  points.forEach((point, i) => i ? ctx.lineTo(point.x, point.y) : ctx.moveTo(point.x, point.y));
  ctx.strokeStyle = "#147a56"; ctx.lineWidth = 2; ctx.stroke();
  ctx.fillStyle = "#147a56";
  points.forEach((point) => { ctx.beginPath(); ctx.arc(point.x, point.y, 2.4, 0, Math.PI * 2); ctx.fill(); });
  const labelEvery = Math.max(1, Math.ceil(chartDaily.length / 7));
  ctx.fillStyle = "#85918c"; ctx.textAlign = "center";
  chartDaily.forEach((d, i) => { if (i % labelEvery === 0 || i === chartDaily.length - 1) ctx.fillText(d.date.slice(5), pad.left + step * (i + .5), height - 7); });
  state.chartPoints = points;
}

function chartPointer(event) {
  if (!state.chartPoints.length) return;
  const rect = event.currentTarget.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const closest = state.chartPoints.reduce((best, point) => Math.abs(point.x - x) < Math.abs(best.x - x) ? point : best);
  const tooltip = $("#chartTooltip");
  tooltip.innerHTML = `${closest.data.date}<br>出库 ${formatNumber(closest.data.sales_qty)} · 退货 ${formatNumber(closest.data.return_qty)} · 净发货 ${formatNumber(closest.net)}`;
  tooltip.style.left = `${closest.x}px`;
  tooltip.style.top = `${Math.max(closest.y, 45)}px`;
  tooltip.classList.remove("hidden");
}

async function openSku(sku, start = $("#startDate").value, end = $("#endDate").value) {
  const drawer = $("#skuDrawer");
  $("#drawerBackdrop").classList.remove("hidden");
  drawer.classList.add("open");
  drawer.setAttribute("aria-hidden", "false");
  $("#drawerSku").textContent = sku;
  $("#drawerTitle").textContent = "正在读取";
  $("#drawerSpec").textContent = "";
  $("#drawerContent").innerHTML = '<div class="loading-state"><div class="spinner"></div><span>正在读取 SKU 明细</span></div>';
  try {
    const detail = await api(`/api/skus/${encodeURIComponent(sku)}?start=${start}&end=${end}`);
    renderSkuDetail(detail);
  } catch (error) {
    $("#drawerContent").innerHTML = `<div class="empty-state"><strong>读取失败</strong><span>${escapeHtml(error.message)}</span></div>`;
  }
}

function renderSkuDetail(detail) {
  const p = detail.product;
  const stock = detail.warehouses.reduce((sum, row) => sum + Number(row.stock_num || 0), 0);
  const available = detail.warehouses.reduce((sum, row) => sum + Number(row.available_num || 0), 0);
  const sales = detail.daily.reduce((sum, row) => sum + Number(row.sales_qty || 0), 0);
  const returns = detail.daily.reduce((sum, row) => sum + Number(row.return_qty || 0), 0);
  $("#drawerTitle").textContent = p.short_name || p.goods_name || "未命名货品";
  $("#drawerSpec").textContent = [p.goods_name, p.spec_name].filter(Boolean).join(" · ") || "-";
  $("#drawerContent").innerHTML = `
    <div class="drawer-metrics">
      <div class="drawer-metric"><span>当前库存</span><strong>${formatNumber(stock)}</strong></div>
      <div class="drawer-metric"><span>可用库存</span><strong>${formatNumber(available)}</strong></div>
      <div class="drawer-metric"><span>净发货</span><strong>${formatNumber(sales - returns)}</strong></div>
    </div>
    <section class="drawer-section">
      <h3>仓库分布</h3>
      ${detail.warehouses.length ? detail.warehouses.map((row) => `<div class="warehouse-row"><strong>${escapeHtml(row.warehouse_name || row.warehouse_no || "未命名仓库")}</strong><span>库存 ${formatNumber(row.stock_num)}</span><span>可用 ${formatNumber(row.available_num)}</span></div>`).join("") : '<span class="muted">暂无仓库库存</span>'}
    </section>
    <section class="drawer-section">
      <h3>最近流水</h3>
      ${detail.recent_movements.length ? detail.recent_movements.map((row) => {
        const qty = Number(row.in_num) > 0 ? `+${formatNumber(row.in_num)}` : `-${formatNumber(row.out_num)}`;
        return `<div class="movement-row"><span>${escapeHtml(row.movement_date)}</span><div><strong>${escapeHtml(row.movement_name || movementName(row.movement_type))}</strong><span> · ${escapeHtml(row.src_order_no || "无单号")}</span></div><strong class="movement-qty ${Number(row.in_num) > 0 ? "" : "net-value"}">${qty}</strong></div>`;
      }).join("") : '<span class="muted">所选日期内没有流水</span>'}
    </section>`;
}

function movementName(type) {
  return ({ "-1": "销售出库", "1": "采购入库", "3": "退货入库", "-2": "调拨出库", "2": "调拨入库" })[String(type)] || "库存变动";
}

function closeDrawer() {
  $("#skuDrawer").classList.remove("open");
  $("#skuDrawer").setAttribute("aria-hidden", "true");
  $("#drawerBackdrop").classList.add("hidden");
}

function openSyncDialog() {
  $("#syncMessage").classList.add("hidden");
  $("#syncDialog").showModal();
}

async function submitSync(event) {
  event.preventDefault();
  const button = $("#syncSubmit");
  const message = $("#syncMessage");
  button.disabled = true;
  button.querySelector("span").textContent = "同步中";
  message.classList.add("hidden");
  try {
    const result = await api("/api/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scope: "inventory" }),
    });
    $("#syncDialog").close();
    showToast(`${result.date} 库存刷新完成：${formatNumber(result.inventory_count)} 条分仓库存`);
    await Promise.all([loadStatus(), loadWarehouses()]);
    state.page = 1;
    await loadDashboard();
  } catch (error) {
    message.textContent = error.message;
    message.classList.remove("hidden");
  } finally {
    button.disabled = false;
    button.querySelector("span").textContent = "开始刷新";
  }
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.remove("hidden");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.add("hidden"), 3500);
}

function refreshIcons() {
  if (window.lucide) window.lucide.createIcons({ attrs: { "stroke-width": 1.8 } });
}

function bindEvents() {
  [$("#warehouseSelect"), $("#stockStatusSelect")].forEach((control) => control.addEventListener("change", () => {
    state.page = 1;
    state.inboundPage = 1;
    state.salesPage = 1;
    state.shopSalesPage = 1;
    state.shortPage = 1;
    state.replenishmentPage = 1;
    state.purchasePlanPage = 1;
    state.transferPlanPage = 1;
    state.clearanceSummaryPage = 1;
    reloadActiveView();
  }));
  $("#searchInput").addEventListener("input", () => {
    clearTimeout(state.searchTimer);
    state.page = 1;
    state.inboundPage = 1;
    state.salesPage = 1;
    state.shopSalesPage = 1;
    state.shortPage = 1;
    state.replenishmentPage = 1;
    state.purchasePlanPage = 1;
    state.transferPlanPage = 1;
    state.clearanceSummaryPage = 1;
    state.searchTimer = setTimeout(reloadActiveView, 280);
  });
  $("#pageSizeSelect").addEventListener("change", (event) => {
    state.pageSize = Number(event.target.value);
    state.page = 1;
    loadDashboard();
  });
  $("#previousPage").addEventListener("click", () => {
    if (state.page > 1) { state.page -= 1; loadDashboard(); }
  });
  $("#nextPage").addEventListener("click", () => {
    state.page += 1;
    loadDashboard();
  });
  $$(".side-nav button[data-view]").forEach((button) => button.addEventListener("click", () => {
    state.activeView = button.dataset.view;
    const pageMeta = {
      dashboard: ["数据看板", "整体仓储与近期经营概览"],
      inventory: ["库存明细", "按仓库、库存状态和 SKU 查询当前库存"],
      inbound: ["入库分析", "按仓库与入库类型分析近期入库流水"],
      sales: ["仓库销量与退货", "按发货仓查看 SKU 销售与退货"],
      shopSales: ["分店铺统计", "按店铺查看每个 SKU 的发货、退货与净销量"],
      shortNames: ["简称汇总", "按商品简称汇总销量与仓库分布"],
      replenishment: ["库存预警", "非清仓款提示含在途库存超过 90 天的积压；清仓款只提示即将清完的库存"],
      purchasePlan: ["采购计划", "按目标仓先调拨后直采；清仓款不参与采购"],
      transferPlan: ["调拨建议", "按 SKU 与仓库安全库存余量生成仓间调拨建议"],
      clearanceSummary: ["清仓汇总", "按销售仓查看清仓库存数量与成本占用"],
    };
    $$(".side-nav button[data-view]").forEach((item) => item.classList.toggle("active", item === button));
    moveFilterToolbar(state.activeView);
    $("#pageTitle").textContent = pageMeta[state.activeView][0];
    $("#pageSubtitle").textContent = pageMeta[state.activeView][1];
    $("#dashboardView").classList.toggle("hidden", state.activeView !== "dashboard");
    $("#inventoryView").classList.toggle("hidden", state.activeView !== "inventory");
    $("#inboundView").classList.toggle("hidden", state.activeView !== "inbound");
    $("#salesView").classList.toggle("hidden", state.activeView !== "sales");
    $("#shopSalesView").classList.toggle("hidden", state.activeView !== "shopSales");
    $("#shortNamesView").classList.toggle("hidden", state.activeView !== "shortNames");
    $("#replenishmentView").classList.toggle("hidden", state.activeView !== "replenishment");
    $("#purchasePlanView").classList.toggle("hidden", state.activeView !== "purchasePlan");
    $("#transferPlanView").classList.toggle("hidden", state.activeView !== "transferPlan");
    $("#clearanceSummaryView").classList.toggle("hidden", state.activeView !== "clearanceSummary");
    $(".status-control").classList.toggle("hidden", !["dashboard", "inventory"].includes(state.activeView));
    $(".alert-status-control").classList.toggle("hidden", state.activeView !== "replenishment");
    $(".purchase-trend-control").classList.toggle("hidden", state.activeView !== "purchasePlan");
    $(".purchase-status-control").classList.toggle("hidden", state.activeView !== "purchasePlan");
    $(".warehouse-control").classList.toggle("hidden", ["shortNames"].includes(state.activeView));
    $(".shop-sales-shop-control").classList.toggle("hidden", state.activeView !== "shopSales");
    $("#exportButton").classList.toggle("hidden", state.activeView !== "inventory");
    reloadActiveView();
  }));
  $$(".dashboard-period button[data-dashboard-days]").forEach((button) => button.addEventListener("click", () => {
    state.dashboardDays = Number(button.dataset.dashboardDays);
    const end = new Date();
    const start = new Date(end);
    start.setDate(start.getDate() - state.dashboardDays + 1);
    $("#startDate").value = localDate(start);
    $("#endDate").value = localDate(end);
    $$(".dashboard-period button").forEach((item) => item.classList.toggle("active", item === button));
    state.page = 1;
    loadDashboard();
  }));
  [$("#inboundStartDate"), $("#inboundEndDate"), $("#inboundTypeSelect")].forEach((control) => control.addEventListener("change", () => {
    state.inboundPage = 1;
    loadInbound();
  }));
  $("#inboundPageSizeSelect").addEventListener("change", (event) => {
    state.inboundPageSize = Number(event.target.value);
    state.inboundPage = 1;
    loadInbound();
  });
  $("#inboundPreviousPage").addEventListener("click", () => {
    if (state.inboundPage > 1) { state.inboundPage -= 1; loadInbound(); }
  });
  $("#inboundNextPage").addEventListener("click", () => {
    state.inboundPage += 1;
    loadInbound();
  });
  [$("#salesStartDate"), $("#salesEndDate")].forEach((control) => control.addEventListener("change", () => {
    state.salesPage = 1;
    loadWarehouseSales();
  }));
  $("#salesPageSizeSelect").addEventListener("change", (event) => {
    state.salesPageSize = Number(event.target.value);
    state.salesPage = 1;
    loadWarehouseSales();
  });
  $("#salesPreviousPage").addEventListener("click", () => {
    if (state.salesPage > 1) { state.salesPage -= 1; loadWarehouseSales(); }
  });
  $("#salesNextPage").addEventListener("click", () => {
    state.salesPage += 1;
    loadWarehouseSales();
  });
  [$("#shopSalesStartDate"), $("#shopSalesEndDate")].forEach((control) => control.addEventListener("change", () => {
    state.shopSalesPage = 1;
    loadShopSales();
  }));
  $("#shopSalesShopSelect").addEventListener("change", () => {
    state.shopSalesPage = 1;
    loadShopSales();
  });
  $("#shopSalesPageSizeSelect").addEventListener("change", (event) => {
    state.shopSalesPageSize = Number(event.target.value);
    state.shopSalesPage = 1;
    loadShopSales();
  });
  $("#shopSalesPreviousPage").addEventListener("click", () => {
    if (state.shopSalesPage > 1) { state.shopSalesPage -= 1; loadShopSales(); }
  });
  $("#shopSalesNextPage").addEventListener("click", () => {
    state.shopSalesPage += 1;
    loadShopSales();
  });
  [$("#shortStartDate"), $("#shortEndDate")].forEach((control) => control.addEventListener("change", () => {
    state.shortPage = 1;
    loadShortNameSales();
  }));
  $("#shortPageSizeSelect").addEventListener("change", (event) => {
    state.shortPageSize = Number(event.target.value);
    state.shortPage = 1;
    loadShortNameSales();
  });
  $("#shortPreviousPage").addEventListener("click", () => {
    if (state.shortPage > 1) { state.shortPage -= 1; loadShortNameSales(); }
  });
  $("#shortNextPage").addEventListener("click", () => {
    state.shortPage += 1;
    loadShortNameSales();
  });
  $("#replenishmentPageSizeSelect").addEventListener("change", (event) => {
    state.replenishmentPageSize = Number(event.target.value);
    state.replenishmentPage = 1;
    loadReplenishment();
  });
  $("#replenishmentPreviousPage").addEventListener("click", () => {
    if (state.replenishmentPage > 1) { state.replenishmentPage -= 1; loadReplenishment(); }
  });
  $("#replenishmentNextPage").addEventListener("click", () => {
    state.replenishmentPage += 1;
    loadReplenishment();
  });
  $("#replenishmentEndDate").addEventListener("change", () => {
    state.replenishmentPage = 1;
    loadReplenishment();
  });
  $("#alertStatusSelect").addEventListener("change", () => {
    state.replenishmentPage = 1;
    loadReplenishment();
  });
  $$("[data-replenishment-mode]").forEach((button) => button.addEventListener("click", () => {
    state.replenishmentMode = button.dataset.replenishmentMode;
    $$("[data-replenishment-mode]").forEach((item) => item.classList.toggle("active", item === button));
    // A status from the other mode must not silently narrow the new mode.
    $("#alertStatusSelect").value = "";
    state.replenishmentPage = 1;
    loadReplenishment();
  }));
  $("#purchasePlanPageSizeSelect").addEventListener("change", (event) => {
    state.purchasePlanPageSize = Number(event.target.value);
    state.purchasePlanPage = 1;
    loadPurchasePlan();
  });
  $("#purchasePlanPreviousPage").addEventListener("click", () => {
    if (state.purchasePlanPage > 1) { state.purchasePlanPage -= 1; loadPurchasePlan(); }
  });
  $("#purchasePlanNextPage").addEventListener("click", () => {
    state.purchasePlanPage += 1;
    loadPurchasePlan();
  });
  $("#purchasePlanEndDate").addEventListener("change", () => {
    state.purchasePlanPage = 1;
    loadPurchasePlan();
  });
  $("#purchaseTrendSelect").addEventListener("change", () => {
    state.purchasePlanPage = 1;
    loadPurchasePlan();
  });
  $("#purchaseStatusSelect").addEventListener("change", () => {
    state.purchasePlanPage = 1;
    loadPurchasePlan();
  });
  $("#transferPlanPageSizeSelect").addEventListener("change", (event) => {
    state.transferPlanPageSize = Number(event.target.value);
    state.transferPlanPage = 1;
    loadTransferPlan();
  });
  $("#transferPlanPreviousPage").addEventListener("click", () => {
    if (state.transferPlanPage > 1) { state.transferPlanPage -= 1; loadTransferPlan(); }
  });
  $("#transferPlanNextPage").addEventListener("click", () => {
    state.transferPlanPage += 1;
    loadTransferPlan();
  });
  $("#transferPlanEndDate").addEventListener("change", () => {
    state.transferPlanPage = 1;
    loadTransferPlan();
  });
  $("#clearanceSummaryPageSizeSelect").addEventListener("change", (event) => {
    state.clearanceSummaryPageSize = Number(event.target.value);
    state.clearanceSummaryPage = 1;
    loadClearanceSummary();
  });
  $("#clearanceSummaryPreviousPage").addEventListener("click", () => {
    if (state.clearanceSummaryPage > 1) { state.clearanceSummaryPage -= 1; loadClearanceSummary(); }
  });
  $("#clearanceSummaryNextPage").addEventListener("click", () => {
    state.clearanceSummaryPage += 1;
    loadClearanceSummary();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "/" && document.activeElement.tagName !== "INPUT") { event.preventDefault(); $("#searchInput").focus(); }
    if (event.key === "Escape") closeDrawer();
  });
  $$('th button[data-sort]').forEach((button) => button.addEventListener("click", () => {
    const key = button.dataset.sort;
    state.sort = { key, direction: state.sort.key === key && state.sort.direction === "desc" ? "asc" : "desc" };
    renderTable();
  }));
  $("#syncButton").addEventListener("click", openSyncDialog);
  $("#syncForm").addEventListener("submit", submitSync);
  $("#drawerClose").addEventListener("click", closeDrawer);
  $("#drawerBackdrop").addEventListener("click", closeDrawer);
  $("#trendChart").addEventListener("pointermove", chartPointer);
  $("#trendChart").addEventListener("pointerleave", () => $("#chartTooltip").classList.add("hidden"));
  window.addEventListener("resize", () => {
    if (state.data && state.activeView === "dashboard") drawChart(state.data.daily || []);
  });
}

async function initialize() {
  setDefaultDates(30);
  setDefaultSalesDates();
  moveFilterToolbar(state.activeView);
  bindEvents();
  refreshIcons();
  try {
    await Promise.all([loadStatus(), loadWarehouses()]);
    await loadDashboard();
  } catch (error) {
    showToast(error.message);
  }
}

initialize();
