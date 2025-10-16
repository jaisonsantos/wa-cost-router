import { test, expect } from '@playwright/test';

test('billing portal opens when clicking manage subscription', async ({ page }) => {
  // Mock API response for /billing/portal
  await page.route('http://localhost:8000/billing/portal', route => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ url: 'https://stripe.test/portal' }),
    });
  });

  // Mock billing summary so the page shows the button enabled
  await page.route('http://localhost:8000/billing/summary', route => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ price_id: 'price_123', plan_status: 'active', price_amount_minor: 1000, price_currency: 'eur' }),
    });
  });

  // Go to settings
  await page.goto('http://localhost:5173/settings');

  // Wait for button and click
  const btn = page.getByRole('button', { name: /Gerenciar assinatura|Alterar Plano/i });
  await btn.click();

  // Expect navigation to stripe portal URL
  await expect(page).toHaveURL('https://stripe.test/portal');
});
