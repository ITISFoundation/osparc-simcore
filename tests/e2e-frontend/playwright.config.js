/* eslint-disable no-undef */

const { defineConfig, devices } = require('@playwright/test');

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
  /* Do not run tests in files in parallel */
  fullyParallel: false,
  /* And make sure they run one after the other */
  workers: 1,
  /* Reporter to use. See https://playwright.dev/docs/test-reporters */
  reporter: 'html',
  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  use: {
    /* Basic Options */
    // Base URL to use in actions like `await page.goto('/')`
    // baseURL: 'http://127.0.0.1:9081',

    /* Emulation Options */
    // oSPARC min: HD 1280x720
    viewport: {
      width: 1280,
      height: 720
    },

    /* Recording Options */
    screenshot: 'only-on-failure',
    // Collect trace when retrying the failed test. See https://playwright.dev/docs/trace-viewer
    trace: 'retain-on-failure',
    video: 'off',

    /* Other Options */
    // Name of the browser that runs tests. For example `chromium`, `firefox`, `webkit`.
    // browserName: 'chromium',
    // Run browser in headless mode.
    // headless: false,
    // Change the default data-testid attribute.
    testIdAttribute: 'osparc-test-id',

    /* More browser and context options */
    launchOptions: {
      slowMo: 50,
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
