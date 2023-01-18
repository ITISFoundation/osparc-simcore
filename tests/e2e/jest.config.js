const config = {
  preset: "jest-puppeteer",
  verbose: true,
  collectCoverage: true,
  coverageReporters: ["lcov", "text"],
  setupFiles: ['<rootDir>/custom-jest-setup.ts'],
};

module.exports = config;
