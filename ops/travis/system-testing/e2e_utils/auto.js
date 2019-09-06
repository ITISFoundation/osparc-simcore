async function register(page, user, pass) {
  await page.waitForSelector('#loginCreateAccountBtn');
  await page.click('#loginCreateAccountBtn');

  await page.waitFor(1000);
  await page.waitFor(1000);
  console.log(await page.content());

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
  else {
    await page.waitForSelector('#loginUserEmailFld');
    await page.type('#loginUserEmailFld', user);
    await page.waitForSelector('#loginPasswordFld');
    await page.type('#loginPasswordFld', pass);
    await page.waitForSelector('#loginSubmitBtn');
    await page.click('#loginSubmitBtn');
  }
}

async function logOut(page) {
  // user might be already logged in
  const elementExists = await page.$("#userMenuMainBtn");
  if (elementExists === null) {
    return;
  }
  await page.waitForSelector('#userMenuMainBtn');
  await page.click('#userMenuMainBtn');

  await page.waitForSelector('#userMenuLogoutBtn');
  await page.click('#userMenuLogoutBtn');
}

async function dashboardAbout(page) {
  await page.waitForSelector('#userMenuMainBtn');
  await page.click('#userMenuMainBtn');

  await page.waitForSelector('#userMenuAboutBtn');
  await page.click('#userMenuAboutBtn');

  await page.waitForSelector('#aboutWindowCloseBtn');
  await page.click('#aboutWindowCloseBtn');
}

async function dashboardPreferences(page) {
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

async function dashboardEditStudyThumbnail(page) {
  await page.waitForSelector('div > div > div > #studiesTabBtn > div')
  await page.click('div > div > div > #studiesTabBtn > div')

  await page.waitForSelector('div > div > div > #editStudyBtn > div:nth-child(1)')
  await page.click('div > div > div > #editStudyBtn > div:nth-child(1)')

  await page.waitForSelector('div #studyDetailsEditorThumbFld')
  await page.click('div #studyDetailsEditorThumbFld')
  await page.type('div #studyDetailsEditorThumbFld', 'https://i.ytimg.com/vi/Oj3aB_wMtno/hqdefault.jpg')

  await page.waitForSelector('div #studyDetailsEditorSaveBtn')
  await page.click('div #studyDetailsEditorSaveBtn')
}

async function dashboardNewStudy(page) {
  await page.waitForSelector('div > div > div > #studiesTabBtn > div')
  await page.click('div > div > div > #studiesTabBtn > div')

  await page.waitFor('#newStudyBtn');
  await page.click('#newStudyBtn');

  await page.waitFor('#newStudyTitleFld');
  await page.type('#newStudyTitleFld', 'my new study');
  await page.type('#newStudyDescFld', 'this is puppeteer creating a new study');

  await page.click('#newStudySubmitBtn');
}

async function dashboardOpenFirstTemplateAndRun(page, templateName) {
  await page.waitForSelector('div > div > div > #studiesTabBtn > div')
  await page.click('div > div > div > #studiesTabBtn > div')

  if (templateName) {
    await __dashboardFilterStudiesByText(page, templateName);
  }

  await page.waitForSelector('div > div > #templateStudiesList > .qx-pb-listitem:nth-child(1) > img')
  await page.click('div > div > #templateStudiesList > .qx-pb-listitem:nth-child(1) > img')

  await page.waitForSelector('div > div > div > #openStudyBtn > div')
  await page.click('div > div > div > #openStudyBtn > div')

  await page.waitForSelector('#newStudySubmitBtn')
  await page.click('#newStudySubmitBtn')

  await page.waitForSelector('div > div > div > #runStudyBtn > div:nth-child(1)')
  await page.click('div > div > div > #runStudyBtn > div:nth-child(1)')

  await page.waitFor(20000);

  await page.waitForSelector('div > div > div > #dashboardBtn > div')
  await page.click('div > div > div > #dashboardBtn > div')
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
  await page.waitForSelector('div > div > div > #studiesTabBtn > div')
  await page.click('div > div > div > #studiesTabBtn > div')

  await page.waitForSelector('div > div > #userStudiesList > .qx-pb-listitem:nth-child(1) > img')
  await page.click('div > div > #userStudiesList > .qx-pb-listitem:nth-child(1) > img')

  await page.waitForSelector('div > div > div > #deleteStudiesBtn > div:nth-child(1)')
  await page.click('div > div > div > #deleteStudiesBtn > div:nth-child(1)')

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
  dashboardEditStudyThumbnail,
  dashboardNewStudy,
  dashboardOpenFirstTemplateAndRun,
  dashboardDeleteFirstStudy,
}
