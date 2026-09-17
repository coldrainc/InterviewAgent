import { test, expect } from "../fixtures/app.fixture.js";

test.describe("guest access gate", () => {
  test.beforeEach(async ({ app }) => {
    await app.open();
  });

  test("keeps private product areas behind login", async ({ app, page }) => {
    await app.expectGuestGate();
    await expect(page.getByRole("button", { name: /刷题训练/ })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /复习站/ })).toHaveCount(0);
    await app.expectNoSensitiveText();
    await app.expectNoHorizontalOverflow();
  });

  test("persists the selected light or dark theme", async ({ app, page }) => {
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await app.toggleTheme();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  });
});
