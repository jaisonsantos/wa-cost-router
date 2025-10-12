import { test, expect, APIRequestContext, Page, Route } from "@playwright/test";

const API_BASE_URL = process.env.E2E_API_BASE_URL ?? "http://localhost:8000";
const DEMO_EMAIL = process.env.E2E_DEMO_EMAIL ?? "admin@demo.local";
const DEMO_PASSWORD = process.env.E2E_DEMO_PASSWORD ?? "demo123";

type IntegrationConnection = {
  id: string;
  channel: string;
  status: string;
  connected: boolean;
  has_credentials: boolean;
  metadata?: Record<string, unknown>;
  last_health_check?: {
    healthy: boolean;
    status_code?: string | number | null;
    latency_ms?: number | null;
    error?: string | null;
    checked_at?: string | null;
    details?: Record<string, unknown>;
  } | null;
};

async function authenticate(request: APIRequestContext): Promise<string> {
  const response = await request.post(`${API_BASE_URL}/auth/login`, {
    data: { email: DEMO_EMAIL, password: DEMO_PASSWORD },
  });

  expect(response.ok()).toBeTruthy();

  const payload = (await response.json()) as { access_token: string };
  return payload.access_token;
}

async function fetchConnections(
  request: APIRequestContext,
  token: string,
): Promise<IntegrationConnection[]> {
  const response = await request.get(`${API_BASE_URL}/integrations/connections`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  expect(response.ok()).toBeTruthy();
  return (await response.json()) as IntegrationConnection[];
}

function waitForEmailTestResponse(page: Page) {
  return page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().includes("/integrations/email/test"),
  );
}

test.describe("Settings connections", () => {
  test("renders connections and handles sandbox health checks", async ({ page, request }) => {
    const token = await authenticate(request);
    const connections = await fetchConnections(request, token);
    const emailConnection = connections.find((connection) => connection.channel === "email");

    expect(emailConnection).toBeDefined();
    expect(emailConnection?.has_credentials).toBeTruthy();

    await page.addInitScript((authToken: string) => {
      window.localStorage.setItem("token", authToken);
    }, token);

    await page.goto("/settings");
    await expect(page).toHaveURL(/\/settings$/);
    await expect(page.getByRole("heading", { level: 2, name: "Configurações" })).toBeVisible();

    const emailCardHeader = page.getByRole("heading", { name: "Email (SMTP)" }).locator("..");
    const emailTestButton = page.getByRole("button", { name: "Testar Email" });

    await Promise.all([waitForEmailTestResponse(page), emailTestButton.click()]);
    await expect(page.getByText("Conexão saudável")).toBeVisible();
    await expect(emailCardHeader.getByText("Saudável")).toBeVisible();
    await page.keyboard.press("Escape");

    const failureCheckedAt = new Date().toISOString();

    await page.route(
      "**/integrations/connections",
      async (route: Route) => {
        const upstream = await route.fetch();
        const payload = (await upstream.json()) as IntegrationConnection[];
        const patched = payload.map((connection) => {
          if (connection.channel !== "email") {
            return connection;
          }
          return {
            ...connection,
            status: "error",
            last_health_check: {
              healthy: false,
              status_code: 503,
              latency_ms: 215,
              error: "Sandbox simulated failure",
              checked_at: failureCheckedAt,
              details: { mode: "sandbox" },
            },
          };
        });

        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(patched),
        });
      },
      { times: 1 },
    );

    await page.route(
      "**/integrations/email/test",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            channel: "email",
            status: "error",
            healthy: false,
            status_code: 503,
            latency_ms: 215,
            error: "Sandbox simulated failure",
            checked_at: failureCheckedAt,
            metadata: emailConnection?.metadata ?? {},
          }),
        });
      },
      { times: 1 },
    );

    await Promise.all([waitForEmailTestResponse(page), emailTestButton.click()]);
    await expect(page.getByText("Falha no teste da conexão", { exact: true }).first()).toBeVisible();
    await expect(emailCardHeader.getByText("Falha")).toBeVisible();
    await page.keyboard.press("Escape");
  });
});
