const demo = false;

module.exports = {
  launch: {
    headless: !demo,
    slowMo: demo ? 60 : 0,
    defaultViewport: null,
    devtools: true
  }
}
