import { defineConfig } from "@playwright/test";

const baseURL = process.env.BASE_URL || "http://localhost:8100";

export default defineConfig({
  testDir: ".",
  timeout: 90_000,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL,
    trace: "retain-on-failure",
  },
});
