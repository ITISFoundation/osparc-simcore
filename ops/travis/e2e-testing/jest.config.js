module.exports = {
  preset: "jest-puppeteer",
  verbose: true,
  globals: {
    url: "http://localhost:9081/",
    goToTimeout: 15000,
  }
}
