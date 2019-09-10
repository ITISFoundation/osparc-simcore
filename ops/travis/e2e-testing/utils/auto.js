const utils = require("./utils")

async function register(page, user, pass) {
  await page.waitForSelector('#loginCreateAccountBtn');
  await page.click('#loginCreateAccountBtn');

  console.log("Registering:", user);
  await page.waitForSelector('#registrationEmailFld');
  await page.type('#registrationEmailFld', user);
  await page.type('#registrationPass1Fld', pass);
  await page.type('#registrationPass2Fld', pass);
  await page.waitForSelector('#registrationSubmitBtn');
  await page.click('#registrationSubmitBtn');
}

async function logIn(page, user, pass) {
  // user might be already logged in
  const elementExists = await page.$("#userMenuMainBtn");
  if (elementExists !== null) {
    return;
  }

  console.log("Logging in:", user);
  await page.waitForSelector('#loginUserEmailFld', {
    visible: true
  });
  await page.type('#loginUserEmailFld', user);
  await page.waitForSelector('#loginPasswordFld');
  await page.type('#loginPasswordFld', pass);
  await page.waitForSelector('#loginSubmitBtn');
  await page.click('#loginSubmitBtn');
}

async function logOut(page) {
  await page.waitForSelector('#userMenuMainBtn', {
    visible: true,
    timeout: 1000
  });

  console.log("Logging out");
  await page.waitForSelector('#userMenuMainBtn');
  await page.click('#userMenuMainBtn');
  await page.waitForSelector('#userMenuLogoutBtn');
  await page.click('#userMenuLogoutBtn');
}

async function dashboardAbout(page) {
  console.log("Showing About");

  await page.waitForSelector('#userMenuMainBtn');
  await page.click('#userMenuMainBtn');

  await page.waitForSelector('#userMenuAboutBtn');
  await page.click('#userMenuAboutBtn');

  await page.waitForSelector('#aboutWindowCloseBtn');
  await page.click('#aboutWindowCloseBtn');
}

async function dashboardPreferences(page) {
  console.log("Navigating through Preferences");

  await page.waitForSelector('#userMenuMainBtn');
  await page.click('#userMenuMainBtn');

  await page.waitForSelector('#userMenuPreferencesBtn');
  await page.click('#userMenuPreferencesBtn');

  await page.waitForSelector('#preferencesProfileTabBtn');
  await page.click('#preferencesProfileTabBtn');

  await page.waitForSelector('#preferencesSecurityTabBtn');
  await page.click('#preferencesSecurityTabBtn');

  await page.waitForSelector('#preferencesExperimentalTabBtn');
  await page.click('#preferencesExperimentalTabBtn');

  await page.waitForSelector('#preferencesWindowCloseBtn');
  await page.click('#preferencesWindowCloseBtn');
}

async function dashboardServiceBrowser(page) {
  console.log("Navigating through Services");

  await page.waitForSelector('#servicesTabBtn')
  await page.click('#servicesTabBtn')

  await page.waitForSelector('div > div > div > .qx-no-radius-button:nth-child(1) > div:nth-child(1)')
  await page.click('div > div > div > .qx-no-radius-button:nth-child(1) > div:nth-child(1)')

  await page.waitForSelector('div > div > div > div > .qx-no-radius-button:nth-child(3)')
  await page.click('div > div > div > div > .qx-no-radius-button:nth-child(3)')

  await page.waitForSelector('div > div > div > div > .qx-no-radius-button:nth-child(6)')
  await page.click('div > div > div > div > .qx-no-radius-button:nth-child(6)')

  await page.waitForSelector('div > div > div > div > .qx-no-radius-button:nth-child(9)')
  await page.click('div > div > div > div > .qx-no-radius-button:nth-child(9)')

  await page.waitForSelector('#serviceBrowserVersionsDrpDwn')
  await page.click('#serviceBrowserVersionsDrpDwn')

  await page.waitForSelector('.qx-popup > div > div > div > div:nth-child(1)')
  await page.click('.qx-popup > div > div > div > div:nth-child(1)')

  await page.waitForSelector('#serviceBrowserVersionsDrpDwn')
  await page.click('#serviceBrowserVersionsDrpDwn')

  await page.waitForSelector('.qx-popup > div > div > div > div:nth-child(2)')
  await page.click('.qx-popup > div > div > div > div:nth-child(2)')

  await page.waitForSelector('div > .qx-panelview > div:nth-child(1) > div > div')
  await page.click('div > .qx-panelview > div:nth-child(1) > div > div')

  await page.waitForSelector('div > .qx-panelview > div:nth-child(1) > div > div')
  await page.click('div > .qx-panelview > div:nth-child(1) > div > div')
}

async function dashboardDataBrowser(page) {
  console.log("Navigating through Data");

  await page.waitForSelector('div > div > div > #dataTabBtn > div')
  await page.click('div > div > div > #dataTabBtn > div')

  await page.waitFor(2000);
  /*
  await page.waitForSelector('.qx-no-border > div > div > div > div:nth-child(2) > div:nth-child(1)')
  await page.click('.qx-no-border > div > div > div > div:nth-child(2) > div:nth-child(1)')

  await page.waitForSelector('.qx-no-border > div > div > div > div:nth-child(3) > div:nth-child(1)')
  await page.click('.qx-no-border > div > div > div > div:nth-child(3) > div:nth-child(1)')
  */
}

async function dashboardStudyBrowser(page) {
  console.log("Navigating through Studies");

  await page.waitForSelector('div > div > div > #studiesTabBtn > div')
  await page.click('div > div > div > #studiesTabBtn > div')

  await page.waitForSelector('div > div > #templateStudiesList > .qx-pb-listitem:nth-child(1) > img')
  await page.click('div > div > #templateStudiesList > .qx-pb-listitem:nth-child(1) > img')

  await page.waitForSelector('div > div > #templateStudiesList > .qx-pb-listitem:nth-child(2) > img')
  await page.click('div > div > #templateStudiesList > .qx-pb-listitem:nth-child(2) > img')

  await page.waitForSelector('div > div > #templateStudiesList > .qx-pb-listitem:nth-child(1) > img')
  await page.click('div > div > #templateStudiesList > .qx-pb-listitem:nth-child(1) > img')

  await page.waitForSelector('div > div > #templateStudiesList > .qx-pb-listitem:nth-child(2) > img')
  await page.click('div > div > #templateStudiesList > .qx-pb-listitem:nth-child(2) > img')
}

async function dashboardEditFristStudyThumbnail(page) {
  console.log("Editing thumbnail")

  await page.waitForSelector('#studiesTabBtn')
  await page.click('#studiesTabBtn')

  const children = await utils.getVisibleChildrenIDs(page, '#userStudiesList');
  if (children.length === 0) {
    console.log("Editing thumbnail: no study found")
    return
  }
  const firstChildId = '#' + children[0]
  await page.waitForSelector(firstChildId)
  await page.click(firstChildId)

  await page.waitForSelector('#editStudyBtn')
  await page.click('#editStudyBtn')

  await page.waitForSelector('#studyDetailsEditorThumbFld')
  await page.click('#studyDetailsEditorThumbFld')
  await page.type('#studyDetailsEditorThumbFld', 'https://i.ytimg.com/vi/Oj3aB_wMtno/hqdefault.jpg')

  await page.waitForSelector('#studyDetailsEditorSaveBtn')
  await page.click('#studyDetailsEditorSaveBtn')
}

async function dashboardNewStudy(page) {
  console.log("Creating New Study");

  await page.waitForSelector('#studiesTabBtn')
  await page.click('#studiesTabBtn')

  await page.waitFor('#newStudyBtn');
  await page.click('#newStudyBtn');

  await page.waitFor('#newStudyTitleFld');
  await page.type('#newStudyTitleFld', 'my new study');
  await page.type('#newStudyDescFld', 'this is puppeteer creating a new study');

  await page.click('#newStudySubmitBtn');
}

async function toDashboard(page) {
  console.log("To Dashboard");

  await page.waitForSelector('#dashboardBtn')
  await page.click('#dashboardBtn')
}

async function dashboardOpenFirstTemplateAndRun(page, templateName) {
  console.log("Creating New Study from template and running it");

  await page.waitForSelector('#studiesTabBtn')
  await page.click('#studiesTabBtn')

  if (templateName) {
    await __dashboardFilterStudiesByText(page, templateName);
  }

  const children = await utils.getVisibleChildrenIDs(page, '#templateStudiesList');
  if (children.length === 0) {
    console.log("Creating New Study from template and running it: no template found");
    return;
  }
  const firstChildId = '#' + children[0]
  await page.waitForSelector(firstChildId)
  await page.click(firstChildId)

  await page.waitForSelector('#openStudyBtn')
  await page.click('#openStudyBtn')

  await page.waitForSelector('#newStudyTitleFld')
  await page.type('#newStudyTitleFld', ' testing');

  await page.waitForSelector('#newStudySubmitBtn')
  await page.click('#newStudySubmitBtn')

  await page.waitForSelector('#runStudyBtn')
  await page.click('#runStudyBtn')

  await page.waitFor(20000);
}

async function __dashboardFilterStudiesByText(page, templateName) {
  await page.waitFor(1000)
  await page.waitFor('#studyFiltersTextFld')
  await page.click('#studyFiltersTextFld')
  await page.type('#studyFiltersTextFld', templateName)
  await page.keyboard.press('Enter')
  await page.waitFor(1000)
}

async function dashboardDeleteFirstStudy(page) {
  await page.waitForSelector('#studiesTabBtn')
  await page.click('#studiesTabBtn')

  await page.waitForSelector('#userStudiesList > .qx-pb-listitem:nth-child(1)')
  await page.click('#userStudiesList > .qx-pb-listitem:nth-child(1)')

  await page.waitForSelector('#deleteStudiesBtn')
  await page.click('#deleteStudiesBtn')

  await page.waitForSelector('#confirmDeleteStudyBtn')
  await page.click('#confirmDeleteStudyBtn')
}

module.exports = {
  register,
  logIn,
  logOut,
  dashboardAbout,
  dashboardPreferences,
  dashboardServiceBrowser,
  dashboardDataBrowser,
  dashboardStudyBrowser,
  dashboardEditFristStudyThumbnail,
  dashboardNewStudy,
  dashboardOpenFirstTemplateAndRun,
  dashboardDeleteFirstStudy,
  toDashboard,
}
