module.exports = {
  preset: "jest-puppeteer",
  verbose: true,
  collectCoverage: true,
  coverageReporters: ["lcov", "text"],
  // this is needed to access the document in the tests
  testEnvironment: "jsdom",
  globals: {
    url: "http://127.0.0.1:9081/", // For local testing, set your deployed url here
    apiVersion: 'v0/',
    ourTimeout: 40000,
  }
}
