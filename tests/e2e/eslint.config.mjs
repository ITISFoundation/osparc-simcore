import globals from "globals";

export default [{
  languageOptions: {
    globals: {
      ...globals.jest,
      ...globals.node,
      ...globals.browser,
      page: true,
      browser: true,
      context: true,
      jestPuppeteer: true,
      console: true,
      url: true,
      apiVersion: true,
      ourTimeout: true,
    },
  },

  rules: {
    "no-console": "off",
  },
}];