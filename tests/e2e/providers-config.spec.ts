import { test, expect, APIRequestContext } from "@playwright/test";

const API_BASE_URL = process.env.E2E_API_BASE_URL ?? "http://localhost:8000";
const DEMO_EMAIL = process.env.E2E_DEMO_EMAIL ?? "admin@demo.local";
const DEMO_PASSWORD = process.env.E2E_DEMO_PASSWORD ?? "demo123";

type ProviderResponse = {
  id: string;
  name: string;
  type: string;
  status: string;
  is_configured: boolean;
  has_credentials: boolean;
  metadata: Record<string, unknown>;
  required_fields: string[];
  provider_form_schema: {
    fields: { key: string; label: string }[];
    consent_guidance?: string[];
  };
};

async function authenticate(request: APIRequestContext): Promise<string> {
  const response = await request.post(`${API_BASE_URL}/auth/login`, {
    data: { email: DEMO_EMAIL, password: DEMO_PASSWORD },
  });
  expect(response.ok()).toBeTruthy();
  const payload = (await response.json()) as { access_token: string };
  return payload.access_token;
}

async function fetchProviders(request: APIRequestContext, token: string): Promise<ProviderResponse[]> {
  const response = await request.get(`${API_BASE_URL}/providers`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as ProviderResponse[];
}

test.describe("Providers configuration", () => {
  test("configures Twilio sandbox dynamically and validates health", async ({ page, request }) => {
    const token = await authenticate(request);
    const providers = await fetchProviders(request, token);
    const twilio = providers.find((provider) => provider.type === "sms");
    expect(twilio).toBeDefined();

    let twilioId = twilio?.id ?? "";
    let providersCallCount = 0;

    await page.addInitScript((authToken: string) => {
      window.localStorage.setItem("token", authToken);
    }, token);

    await page.route("**/providers", async (route) => {
      const resourceType = route.request().resourceType();
      if (resourceType === "document") {
        await route.continue();
        return;
      }
      providersCallCount += 1;
      const upstream = await route.fetch();
      const payload = (await upstream.json()) as ProviderResponse[];
      const patched = payload.map((provider) => {
        if (provider.id === twilioId) {
          return {
            ...provider,
            is_configured: providersCallCount > 1,
            has_credentials: providersCallCount > 1,
          };
        }
        return provider;
      });
      const currentTwilio = patched.find((provider) => provider.id === twilioId);
      if (currentTwilio) {
        twilioId = currentTwilio.id;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(patched),
      });
    });

    await page.route("**/providers/credentials", async (route) => {
      const body = JSON.parse(route.request().postData() ?? "{}");
      expect(body.credentials.account_sid).toMatch(/^AC[0-9A-F]{32}$/);
      expect(body.credentials.from_number).toMatch(/^\+1\d{10}$/);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "credentials_saved" }),
      });
    });

    await page.route("**/providers/*/health", async (route) => {
      expect(route.request().url()).toContain(twilioId);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          provider_id: twilioId,
          healthy: true,
          latency_ms: 210,
          status_code: 200,
        }),
      });
    });

    await page.goto("/providers");
    await expect(page).toHaveURL(/\/providers$/);

    const twilioCard = page.getByRole("heading", { name: "Twilio Sandbox" }).locator("../../..");
    await expect(twilioCard.getByText("Não configurado")).toBeVisible();

    await twilioCard.getByRole("button", { name: "Configurar" }).click();

    await expect(page.getByText("Twilio SMS Sandbox")).toBeVisible();
    await page.getByLabel("Account SID").fill("AC" + "1".repeat(32));
    await page.getByLabel("Auth Token").fill("A".repeat(32));
    const fromNumber = page.getByLabel("Número remetente (E.164)");
    await fromNumber.fill("15551234567");

    const providerForm = page.getByTestId("provider-form");
    await Promise.all([
      page.waitForRequest((request) =>
        request.url().includes("/providers/credentials") && request.method() === "POST",
      ),
      providerForm.evaluate((form) => (form as HTMLFormElement).requestSubmit()),
    ]);

    await expect(page.getByText(/Credenciais configuradas com sucesso/)).toBeVisible();
    await expect(twilioCard.getByText("Configurado")).toBeVisible();

    await twilioCard.getByRole("button", { name: "Testar" }).click();
    const healthToast = page
      .locator('[data-component-name="ToastTitle"]')
      .filter({ hasText: "Provider está saudável" });
    await expect(healthToast).toBeVisible();

    const sendgridCard = page.getByRole("heading", { name: /SendGrid/i }).locator("../../..");
    await sendgridCard.getByRole("button", { name: "Configurar" }).click();
    const providerDialog = page.getByRole("dialog");
    await expect(providerDialog.getByText("Utilize double opt-in.")).toBeVisible();
    await providerDialog.press("Escape");
    await expect(providerDialog).toBeHidden();
  });
});

