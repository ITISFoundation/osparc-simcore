/* eslint-disable no-undef */

// @ts-check
const {
  defineConfig,
  devices
} = require('@playwright/test');

/**
 * Read environment variables from file.
 * https://github.com/motdotla/dotenv
 */
// require('dotenv').config();

/**
 * @see https://playwright.dev/docs/test-configuration
 */
module.exports = defineConfig({
  testDir: './tests',
  /* Run tests in files in parallel */
  fullyParallel: false,
  /* Reporter to use. See https://playwright.dev/docs/test-reporters */
  reporter: 'html',
  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  use: {
    /* Base URL to use in actions like `await page.goto('/')`. */
    // baseURL: 'http://127.0.0.1:9081',

    /* Collect trace when retrying the failed test. See https://playwright.dev/docs/trace-viewer */
    trace: 'on-first-retry',

    // Name of the browser that runs tests. For example `chromium`, `firefox`, `webkit`.
    // browserName: 'chromium',

    // Run browser in headless mode.
    // headless: false,

    // Change the default data-testid attribute.
    testIdAttribute: 'osparc-test-id',

    launchOptions: {
      slowMo: 50,
    },

    // osparc min: HD 1280x720
    viewport: {
      width: 1280,
      height: 720
    },
  },

  /* Configure projects for major browsers */
  projects: [{
    name: 'chromium',
    use: {
      ...devices['Desktop Chrome']
    },
  }, {
    name: 'firefox',
    use: {
      ...devices['Desktop Firefox']
    },
  }],
});
