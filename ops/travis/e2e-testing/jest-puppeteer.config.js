const demo = false;

module.exports = {
  launch: {
    headless: demo !== 'false',
    slowMo: demo ? 60 : 0,
    devtools: true
  }
}
