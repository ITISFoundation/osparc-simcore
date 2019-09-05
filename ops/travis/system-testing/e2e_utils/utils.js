async function getPageTitle(page) {
  return await page.title();
}

module.exports = {
  getPageTitle,
}
