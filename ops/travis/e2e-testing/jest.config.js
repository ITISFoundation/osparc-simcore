module.exports = {
  preset: "jest-puppeteer",
  verbose: true,
  globals: {
    url: "http://localhost:9081/",
    ourTimeout: 20000,
  }
}
