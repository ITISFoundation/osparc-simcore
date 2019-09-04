const startBrowser = require('./startBrowser');
const auto = require('./auto');

const demo = true;
const browser = await startBrowser.launch(demo);

const page = await browser.newPage();
const url = "http://localhost:9081/"
await page.goto(url);

const randUser = Math.random().toString(36).substring(7);
const userEmail = 'puppeteer_'+randUser+'@itis.testing';
const pass = Math.random().toString(36).substring(7);

page.on('response', response => {
  if (response.url().endsWith("register")) {
    const respStatus = response.status();
    expect(respStatus).toBe(200);
  }
});
await auto.register(page, userEmail, pass);

page.on('response', response => {
  if (response.url().endsWith("services")) {
    const respStatus = response.status();
    expect(respStatus).toBe(200);
  }
  else if (response.url().endsWith("locations")) {
    const respStatus = response.status();
    expect(respStatus).toBe(200);
  }
});
await auto.logIn(page, userEmail, pass);

await auto.dashboardAbout(page);
await auto.dashboardServiceBrowser(page);
await auto.dashboardDataBrowser(page);
await auto.dashboardStudyBrowser(page);
// await auto.dashboardEditStudyThumbnail(page);
// await auto.dashboardNewStudy(page);
// await auto.dashboardOpenFirstTemplateAndRun(page, templateName);
// await auto.dashboardDeleteFirstStudy(page);
if (demo) {
  await page.waitFor(2000);
}

await auto.logOut(page);

browser.close();
