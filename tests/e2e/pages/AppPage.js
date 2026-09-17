import { expect } from "@playwright/test";

const forbiddenProductText = [
  /access[ _-]?token/i,
  /refresh[ _-]?token/i,
  /api[ _-]?key/i,
  /authorization:\s*bearer/i,
  /eyJ[a-zA-Z0-9_-]{12,}\.[a-zA-Z0-9_-]{12,}\.[a-zA-Z0-9_-]{8,}/
];

export class AppPage {
  constructor(page) {
    this.page = page;
    this.authGate = page.locator(".auth-gate");
    this.appShell = page.locator(".app-shell");
    this.sidebar = page.locator("#app-sidebar");
    this.mainNavigation = page.getByLabel("主导航");
  }

  async open() {
    await this.page.goto("/", { waitUntil: "domcontentloaded" });
  }

  async expectGuestGate() {
    await expect(this.authGate).toBeVisible();
    await expect(this.page.getByRole("heading", { name: /你的面试准备/ })).toBeVisible();
    await expect(this.sidebar).toHaveCount(0);
  }

  async register(account) {
    await this.expectGuestGate();
    await this.page.getByRole("button", { name: "注册", exact: true }).click();
    await this.page.getByPlaceholder("昵称").fill(account.displayName);
    await this.page.getByPlaceholder("邮箱").fill(account.email);
    await this.page.getByPlaceholder("密码").fill(account.password);
    await this.page.getByRole("button", { name: "注册并领取试用", exact: true }).click();
    await expect(this.appShell).toBeVisible();
    await expect(this.sidebar).toBeVisible();
  }

  async openSection(label) {
    const button = this.mainNavigation.getByRole("button", { name: new RegExp(label) });
    await button.click();
    await expect(button).toHaveClass(/active/);
  }

  async toggleTheme() {
    const lightToDark = this.page.getByRole("button", { name: "切换到夜间模式" });
    const darkToLight = this.page.getByRole("button", { name: "切换到白天模式" });
    if (await lightToDark.isVisible().catch(() => false)) await lightToDark.click();
    else await darkToLight.click();
  }

  async expectNoSensitiveText() {
    const visibleText = await this.page.locator("body").innerText();
    for (const pattern of forbiddenProductText) {
      expect(visibleText, `product UI must not expose ${pattern}`).not.toMatch(pattern);
    }
  }

  async expectNoHorizontalOverflow() {
    const overflow = await this.page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth
    );
    expect(overflow).toBeLessThanOrEqual(1);
  }
}
