async function getPageTitle(page) {
  return await page.title();
}

function getPageUrl(page) {
  return page.url();
}

async function dragAndDrop(page, start, end) {
  await page.mouse.move(start.x, start.y);
  await page.mouse.down();
  
  await page.mouse.move(end.x, end.y);
  await page.mouse.up();
}

module.exports = {
  getPageTitle,
  getPageUrl,
  dragAndDrop,
}
