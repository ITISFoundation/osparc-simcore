module.exports = {
  preset: "jest-puppeteer",
  verbose: true,
  globals: {
    url: "http://127.0.0.1:9081/",
    apiVersion: 'v0/',
    ourTimeout: 20000,
  }
}
