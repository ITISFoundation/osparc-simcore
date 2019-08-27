const puppeteer = require('puppeteer');

const url = "http://localhost:9081/"

async function run () {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();

  await page.goto(url);

  throw Error('here my error');

  const title = await page.title();
  console.log(title);

  await browser.close();
}

run()
  .catch((e) => console.log('err: ' + e));
