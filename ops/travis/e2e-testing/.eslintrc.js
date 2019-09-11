module.exports = {
    env: {
        jest: true,
        node: true,
        browser: true,
        es6: true,
    },
    globals: {
        page: true,
        browser: true,
        context: true,
        jestPuppeteer: true,
        console: true,
        url: true,
        apiVersion: true,
        ourTimeout: true,
    },
    rules: {
        "no-console": "off",
    },
}
