import { expect, test, APIRequestContext } from "@playwright/test";

const API_BASE_URL = process.env.E2E_API_BASE_URL ?? "http://localhost:8000";
const DEMO_EMAIL = process.env.E2E_DEMO_EMAIL ?? "admin@demo.local";
const DEMO_PASSWORD = process.env.E2E_DEMO_PASSWORD ?? "demo123";

type MessageJobDetail = {
  id: string;
  channel: string;
  channel_address?: string | null;
  status: string;
  template_id: string;
};

async function authenticate(request: APIRequestContext): Promise<string> {
  const response = await request.post(`${API_BASE_URL}/auth/login`, {
    data: { email: DEMO_EMAIL, password: DEMO_PASSWORD },
  });

  expect(response.ok()).toBeTruthy();

  const payload = (await response.json()) as { access_token: string };
  return payload.access_token;
}

async function sendMessage(
  request: APIRequestContext,
  token: string,
  payload: Record<string, unknown>,
): Promise<string> {
  const response = await request.post(`${API_BASE_URL}/messages/send`, {
    headers: { Authorization: `Bearer ${token}` },
    data: payload,
  });

  expect(response.ok()).toBeTruthy();

  const body = (await response.json()) as { job_id?: string };
  expect(body.job_id).toBeTruthy();

  return body.job_id!;
}

async function waitForJob(
  request: APIRequestContext,
  token: string,
  jobId: string,
  expectedChannel: string,
): Promise<MessageJobDetail> {
  const transientStatuses = new Set(["pending", "processing"]);

  for (let attempt = 0; attempt < 20; attempt += 1) {
    const response = await request.get(`${API_BASE_URL}/messages/jobs/${jobId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (response.status() === 404) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      continue;
    }

    expect(response.ok()).toBeTruthy();

    const job = (await response.json()) as MessageJobDetail;

    if (job.channel === expectedChannel && !transientStatuses.has(job.status)) {
      return job;
    }

    await new Promise((resolve) => setTimeout(resolve, 1000));
  }

  throw new Error(`Timed out waiting for job ${jobId} on channel ${expectedChannel}`);
}

test.describe("Messages end-to-end", () => {
  test("displays email and SMS jobs after sandbox sends and filters by channel", async ({
    page,
    request,
  }) => {
    const token = await authenticate(request);

    const timestamp = Date.now();
    const emailAddress = `e2e-email-${timestamp}@example.com`;
    const smsSuffix = (timestamp % 1_000_0000).toString().padStart(7, "0");
    const smsNumber = `+1551${smsSuffix}`;

    const emailJobId = await sendMessage(request, token, {
      idempotency_key: `e2e-email-${timestamp}`,
      channel: "email",
      template_id: "email_digest",
      template_category: "UTILITY",
      channel_address: emailAddress,
      country_iso: "US",
      variables: {
        subject: "Resumo diário",
        html_content: "<p>Mensagem automatizada gerada pelo Playwright</p>",
      },
    });

    const smsJobId = await sendMessage(request, token, {
      idempotency_key: `e2e-sms-${timestamp}`,
      channel: "sms",
      template_id: "otp_sms",
      template_category: "UTILITY",
      channel_address: smsNumber,
      country_iso: "BR",
      variables: {
        body_params: ["123456"],
      },
    });

    const emailJob = await waitForJob(request, token, emailJobId, "email");
    const smsJob = await waitForJob(request, token, smsJobId, "sms");

    await page.addInitScript((authToken: string) => {
      window.localStorage.setItem("token", authToken);
    }, token);

    await page.goto("/messages");
    await expect(page).toHaveURL(/\/messages$/);
    await expect(
      page.getByRole("heading", { level: 1, name: "Mensagens" }),
    ).toBeVisible();

    const tableBody = page.locator("table tbody");

    await expect(tableBody).toContainText(emailJob.channel_address ?? "");
    await expect(tableBody).toContainText(smsJob.channel_address ?? "");

    await page.getByRole("combobox", { name: "Filtrar por canal" }).click();
    await page.getByRole("option", { name: "Email" }).click();

    await expect(tableBody).toContainText(emailJob.channel_address ?? "");
    await expect(tableBody).not.toContainText(smsJob.channel_address ?? "");

    await page.getByRole("combobox", { name: "Filtrar por canal" }).click();
    await page.getByRole("option", { name: "Sms" }).click();

    await expect(tableBody).toContainText(smsJob.channel_address ?? "");
    await expect(tableBody).not.toContainText(emailJob.channel_address ?? "");
  });
});
