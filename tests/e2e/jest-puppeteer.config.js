const demo = false;

module.exports = {
  launch: {
    headless: !demo,
    slowMo: demo ? 60 : 0,
    defaultViewport: {
      width: 1440,
      height: 900
    },
    devtools: false
  }
}
