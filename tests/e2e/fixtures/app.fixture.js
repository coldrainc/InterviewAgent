import { expect, test as base } from "@playwright/test";
import { AppPage } from "../pages/AppPage.js";

export const test = base.extend({
  app: async ({ page }, use) => {
    const failures = [];
    page.on("pageerror", (error) => failures.push(`pageerror: ${error.message}`));
    page.on("console", (message) => {
      if (message.type() === "error") failures.push(`console: ${message.text()}`);
    });
    page.on("response", (response) => {
      if (response.status() >= 500 && response.url().includes("/api/")) {
        failures.push(`http ${response.status()}: ${response.url()}`);
      }
    });

    await use(new AppPage(page));
    expect(failures, "browser and API runtime errors").toEqual([]);
  }
});

export { expect } from "@playwright/test";
