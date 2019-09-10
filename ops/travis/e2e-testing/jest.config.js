module.exports = {
  preset: "jest-puppeteer",
  verbose: true,
  globals: {
    url: "http://localhost:9081/",
    apiVersion: 'v0/',
    ourTimeout: 20000,
  }
}
