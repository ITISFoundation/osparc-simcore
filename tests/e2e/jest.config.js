module.exports = {
  preset: "jest-puppeteer",
  verbose: true,
  collectCoverage: true,
  coverageReporters: ["lcov", "text"],
  globals: {
    url: "http://172.16.8.52:9081/",
    apiVersion: 'v0/',
    ourTimeout: 20000,
  }
}
