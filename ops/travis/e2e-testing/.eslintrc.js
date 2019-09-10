module.exports = {
    env: {
        jest: true,
    },
    globals: {
        page: true,
        browser: true,
        context: true,
        jestPuppeteer: true,
        console: true,
        url: true,
        ourTimeout: true,
    },
    rules: {
        "no-console": "off",
    },
}
