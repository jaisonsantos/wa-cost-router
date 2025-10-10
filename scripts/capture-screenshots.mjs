import { chromium } from "@playwright/test";
import { mkdir } from "fs/promises";
import { fileURLToPath } from "url";
import { dirname, resolve } from "path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const outputDir = resolve(__dirname, "../artifacts/screenshots");
await mkdir(outputDir, { recursive: true });

const payload = { sub: "demo-user", org_id: "demo-org" };
const token = `x.${Buffer.from(JSON.stringify(payload)).toString("base64url")}.y`;

const dashboardResponse = {
  total_messages: 1820,
  total_cost_minor: 135000,
  baseline_cost_minor: 210000,
  saved_minor: 75000,
  success_rate: 97.8,
  avg_latency_ms: 1840,
  top_countries: [
    { country: "BR", cost_minor: 88000, count: 950 },
    { country: "US", cost_minor: 28000, count: 420 },
    { country: "MX", cost_minor: 12000, count: 180 },
  ],
  top_templates: [
    { template: "promo_novembro", category: "marketing", cost_minor: 42000, count: 600 },
    { template: "recuperacao_pagamento", category: "utility", cost_minor: 28000, count: 350 },
  ],
  alerts: [
    {
      type: "warning",
      message: "Latência média de 1840ms (ideal < 2000ms)",
      action: "Avalie distribuição para provedores regionais",
    },
  ],
  recommendations: [
    "Você economizou €750.00 nos últimos 7 dias com otimização de rotas",
    "Conecte mais provedores para aumentar resiliência e reduzir custos",
  ],
};

const providerMetrics = [
  {
    provider_id: "meta",
    provider_name: "Meta WhatsApp",
    total_sent: 1200,
    success_rate: 98.5,
    avg_latency_ms: 1500,
    total_cost_minor: 90000,
  },
  {
    provider_id: "twilio",
    provider_name: "Twilio",
    total_sent: 420,
    success_rate: 95.0,
    avg_latency_ms: 2100,
    total_cost_minor: 32000,
  },
];

const rulesPayload = [
  {
    id: "rule-br-primary",
    name: "BR marketing via Meta",
    is_enabled: true,
    priority: 10,
    conditions: [
      { type: "country", values: ["BR"] },
      { type: "category", values: ["marketing"] },
    ],
    actions: { primary_provider: "meta", fallback_chain: ["twilio"] },
  },
  {
    id: "rule-us-fallback",
    name: "Fallback EUA",
    is_enabled: true,
    priority: 20,
    conditions: [{ type: "country", values: ["US"] }],
    actions: { primary_provider: "twilio", fallback_chain: ["meta"] },
  },
];

const providersPayload = [
  {
    id: "meta",
    name: "Meta WhatsApp",
    type: "whatsapp",
    status: "active",
    is_configured: true,
    has_credentials: true,
    avg_latency_ms: 1500,
  },
  {
    id: "twilio",
    name: "Twilio Messaging",
    type: "whatsapp",
    status: "active",
    is_configured: true,
    has_credentials: true,
    avg_latency_ms: 2100,
  },
];

const quickSimulation = { baseline: 150000, optimized: 110000, saved: 40000 };

const browser = await chromium.launch({ args: ["--no-sandbox"] });
const context = await browser.newContext();
const page = await context.newPage();

await page.addInitScript((value) => {
  window.localStorage.setItem("token", value);
}, token);

await page.route("**/*", async (route, request) => {
  const url = request.url();
  if (url.includes("/reports/dashboard-metrics")) {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(dashboardResponse) });
    return;
  }
  if (url.includes("/reports/provider-metrics")) {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(providerMetrics) });
    return;
  }
  if (url.endsWith("/rules") && request.method() === "GET") {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(rulesPayload) });
    return;
  }
  if (url.endsWith("/providers")) {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(providersPayload) });
    return;
  }
  if (url.endsWith("/rules/simulate")) {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(quickSimulation) });
    return;
  }
  if (url.endsWith("/rules/simulate-advanced")) {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(quickSimulation) });
    return;
  }
  await route.continue();
});

await page.goto("http://127.0.0.1:4173/dashboard", { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await page.screenshot({ path: resolve(outputDir, "dashboard-20250210.png"), fullPage: true });

await page.goto("http://127.0.0.1:4173/rules", { waitUntil: "networkidle" });
await page.waitForTimeout(2000);
await page.screenshot({ path: resolve(outputDir, "rules-20250210.png"), fullPage: true });

await browser.close();
