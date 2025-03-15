module.exports = {
  preset: "jest-puppeteer",
  verbose: true,
  collectCoverage: true,
  coverageReporters: ["lcov", "text"],
  globals: {
    url: "http://127.0.0.1.nip.io:9081/", // For local testing, set your deployed url here
    apiVersion: 'v0/',
    ourTimeout: 40000,
  },
  maxWorkers: 1
}
