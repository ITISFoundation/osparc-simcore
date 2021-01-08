const demo = true;

module.exports = {
  launch: {
    headless: !demo,
    slowMo: demo ? 60 : 0,
    defaultViewport: null,
    devtools: false
  }
}
