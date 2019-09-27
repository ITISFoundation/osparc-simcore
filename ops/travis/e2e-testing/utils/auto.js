const utils = require("./utils")

async function register(page, user, pass) {
  await page.waitForSelector('[osparc-test-id="loginCreateAccountBtn"]');
  await page.click('[osparc-test-id="loginCreateAccountBtn');

  console.log("Registering:", user);
  await page.waitForSelector('[osparc-test-id="registrationEmailFld"]');
  await page.type('[osparc-test-id="registrationEmailFld"]', user);
  await page.type('[osparc-test-id="registrationPass1Fld"]', pass);
  await page.type('[osparc-test-id="registrationPass2Fld"]', pass);
  await page.waitForSelector('[osparc-test-id="registrationSubmitBtn"]');
  await page.click('[osparc-test-id="registrationSubmitBtn"]');
}

async function logIn(page, user, pass) {
  // user might be already logged in
  const elementExists = await page.$('[osparc-test-id="userMenuMainBtn"]');
  if (elementExists !== null) {
    return;
  }

  console.log("Logging in:", user);
  await page.waitForSelector('[osparc-test-id="loginUserEmailFld"]', {
    visible: true
  });
  await page.type('[osparc-test-id="loginUserEmailFld"]', user);
  await page.waitForSelector('[osparc-test-id="loginPasswordFld"]');
  await page.type('[osparc-test-id="loginPasswordFld"]', pass);
  await page.waitForSelector('[osparc-test-id="loginSubmitBtn"]');
  await page.click('[osparc-test-id="loginSubmitBtn"]');
}

async function logOut(page) {
  await page.waitForSelector('[osparc-test-id="userMenuMainBtn"]', {
    visible: true,
    timeout: 1000
  });

  console.log("Logging out");
  await page.waitForSelector('[osparc-test-id="userMenuMainBtn"]');
  await page.click('[osparc-test-id="userMenuMainBtn"]');
  await page.waitForSelector('[osparc-test-id="userMenuLogoutBtn"]');
  await page.click('[osparc-test-id="userMenuLogoutBtn"]');
}

async function dashboardAbout(page) {
  console.log("Showing About");

  await page.waitForSelector('[osparc-test-id="userMenuMainBtn"]');
  await page.click('[osparc-test-id="userMenuMainBtn"]');

  await page.waitForSelector('[osparc-test-id="userMenuAboutBtn"]');
  await page.click('[osparc-test-id="userMenuAboutBtn"]');

  await page.waitForSelector('[osparc-test-id="aboutWindowCloseBtn"]');
  await page.click('[osparc-test-id="aboutWindowCloseBtn"]');
}

async function dashboardPreferences(page) {
  console.log("Navigating through Preferences");

  await page.waitForSelector('[osparc-test-id="userMenuMainBtn"]');
  await page.click('[osparc-test-id="userMenuMainBtn"]');

  await page.waitForSelector('[osparc-test-id="userMenuPreferencesBtn"]');
  await page.click('[osparc-test-id="userMenuPreferencesBtn"]');

  await page.waitForSelector('[osparc-test-id="preferencesProfileTabBtn"]');
  await page.click('[osparc-test-id="preferencesProfileTabBtn"]');

  await page.waitForSelector('[osparc-test-id="preferencesSecurityTabBtn"]');
  await page.click('[osparc-test-id="preferencesSecurityTabBtn"]');

  await page.waitForSelector('[osparc-test-id="preferencesExperimentalTabBtn"]');
  await page.click('[osparc-test-id="preferencesExperimentalTabBtn"]');

  await page.waitForSelector('[osparc-test-id="preferencesWindowCloseBtn"]');
  await page.click('[osparc-test-id="preferencesWindowCloseBtn"]');
}

async function dashboardServiceBrowser(page) {
  console.log("Navigating through Services");

  await page.waitForSelector('[osparc-test-id="servicesTabBtn"]')
  await page.click('[osparc-test-id="servicesTabBtn"]')

  await page.waitForSelector('div > div > div > .qx-no-radius-button:nth-child(1) > div:nth-child(1)')
  await page.click('div > div > div > .qx-no-radius-button:nth-child(1) > div:nth-child(1)')

  await page.waitForSelector('div > div > div > div > .qx-no-radius-button:nth-child(3)')
  await page.click('div > div > div > div > .qx-no-radius-button:nth-child(3)')

  await page.waitForSelector('div > div > div > div > .qx-no-radius-button:nth-child(6)')
  await page.click('div > div > div > div > .qx-no-radius-button:nth-child(6)')

  await page.waitForSelector('div > div > div > div > .qx-no-radius-button:nth-child(10)')
  await page.click('div > div > div > div > .qx-no-radius-button:nth-child(10)')

  await page.waitForSelector('[osparc-test-id="serviceBrowserVersionsDrpDwn"]')
  await page.click('[osparc-test-id="serviceBrowserVersionsDrpDwn"]')

  await page.waitForSelector('.qx-popup > div > div > div > div:nth-child(1)')
  await page.click('.qx-popup > div > div > div > div:nth-child(1)')

  await page.waitForSelector('[osparc-test-id="serviceBrowserVersionsDrpDwn"]')
  await page.click('[osparc-test-id="serviceBrowserVersionsDrpDwn"]')

  await page.waitForSelector('.qx-popup > div > div > div > div:nth-child(2)')
  await page.click('.qx-popup > div > div > div > div:nth-child(2)')

  await page.waitForSelector('div > .qx-panelview > div:nth-child(1) > div > div')
  await page.click('div > .qx-panelview > div:nth-child(1) > div > div')

  await page.waitForSelector('div > .qx-panelview > div:nth-child(1) > div > div')
  await page.click('div > .qx-panelview > div:nth-child(1) > div > div')
}

async function dashboardDataBrowser(page) {
  console.log("Navigating through Data");

  await page.waitForSelector('[osparc-test-id="dataTabBtn"]')
  await page.click('[osparc-test-id="dataTabBtn"]')

  // expand first location
  await page.waitForSelector('.qx-no-border > div > div > div > div:nth-child(2) > div:nth-child(1)')
  await page.click('.qx-no-border > div > div > div > div:nth-child(2) > div:nth-child(1)')

  // expand first study
  await page.waitForSelector('.qx-no-border > div > div > div > div:nth-child(3) > div:nth-child(1)')
  await page.click('.qx-no-border > div > div > div > div:nth-child(3) > div:nth-child(1)')

  await page.waitFor(2000)
  /*
  // expand service
  await page.waitForSelector('div:nth-child(1) > div > div > div:nth-child(5) > div:nth-child(3)')
  await page.click('div:nth-child(1) > div > div > div:nth-child(5) > div:nth-child(3)')

  // seelct file
  await page.waitForSelector('div > div:nth-child(2) > div > .qx-toolbar-button-hovered > div:nth-child(1)')
  await page.click('div > div:nth-child(2) > div > .qx-toolbar-button-hovered > div:nth-child(1)')

  await page.waitFor(2000)
  */
}

async function dashboardStudyBrowser(page) {
  console.log("Navigating through Templates");

  await page.waitForSelector('[osparc-test-id="studiesTabBtn"]')
  await page.click('[osparc-test-id="studiesTabBtn"]')

  const children = await utils.getVisibleChildrenIDs(page, '[osparc-test-id="templateStudiesList"]');
  if (children.length === 0) {
    console.log("Editing thumbnail: no study found")
    return
  }
  for (let i=0; i<children.length; i++) {
    const childId = '[osparc-test-id="' + children[i] + '"]'
    await page.waitForSelector(childId)
    await page.click(childId)
  }
}

async function dashboardEditFristStudyThumbnail(page) {
  console.log("Editing thumbnail")

  await page.waitForSelector('[osparc-test-id="studiesTabBtn"]')
  await page.click('[osparc-test-id="studiesTabBtn"]')

  const children = await utils.getVisibleChildrenIDs(page, '[osparc-test-id="userStudiesList"]');
  if (children.length === 0) {
    console.log("Editing thumbnail: no study found")
    return
  }
  const firstChildId = '[osparc-test-id="' + children[0] + '"]'
  await page.waitForSelector(firstChildId)
  await page.click(firstChildId)

  await page.waitForSelector('[osparc-test-id="editStudyBtn"]')
  await page.click('[osparc-test-id="editStudyBtn"]')

  await page.waitForSelector('[osparc-test-id="studyDetailsEditorThumbFld"]')
  await utils.emptyField(page, '[osparc-test-id="studyDetailsEditorThumbFld"]')
  await page.click('[osparc-test-id="studyDetailsEditorThumbFld"]')
  await page.type('[osparc-test-id="studyDetailsEditorThumbFld"]', 'https://i.ytimg.com/vi/Oj3aB_wMtno/hqdefault.jpg')

  await page.waitForSelector('[osparc-test-id="studyDetailsEditorSaveBtn"]')
  await page.click('[osparc-test-id="studyDetailsEditorSaveBtn"]')
}

async function dashboardNewStudy(page) {
  console.log("Creating New Study");

  await page.waitForSelector('[osparc-test-id="studiesTabBtn"]')
  await page.click('[osparc-test-id="studiesTabBtn"]')

  await page.waitFor('[osparc-test-id="newStudyBtn"]');
  await page.click('[osparc-test-id="newStudyBtn"]');

  await page.waitFor('[osparc-test-id="newStudyTitleFld"]');
  await page.type('[osparc-test-id="newStudyTitleFld"]', 'puppeteering study');
  await page.type('[osparc-test-id="newStudyDescFld"]', 'this is puppeteer creating a new study');

  await page.click('[osparc-test-id="newStudySubmitBtn"]');
}

async function toDashboard(page) {
  console.log("To Dashboard");

  await page.waitForSelector('[osparc-test-id="dashboardBtn"]')
  await page.click('[osparc-test-id="dashboardBtn"]')
}

async function dashboardOpenFirstTemplateAndRun(page, templateName) {
  console.log("Creating New Study from template and running it");

  await page.waitForSelector('[osparc-test-id="studiesTabBtn"]')
  await page.click('[osparc-test-id="studiesTabBtn"]')

  if (templateName) {
    await __dashboardFilterStudiesByText(page, templateName);
  }

  const children = await utils.getVisibleChildrenIDs(page, '[osparc-test-id="templateStudiesList"]');
  if (children.length === 0) {
    console.log("Creating New Study from template and running it: no template found");
    return;
  }
  const firstChildId = '[osparc-test-id="' + children[0] + '"]'
  await page.waitForSelector(firstChildId)
  await page.click(firstChildId)

  await page.waitForSelector('[osparc-test-id="openStudyBtn"]')
  await page.click('[osparc-test-id="openStudyBtn"]')

  await page.waitForSelector('[osparc-test-id="newStudyTitleFld"]')
  await utils.emptyField(page, '[osparc-test-id="newStudyTitleFld"]')
  await page.type('[osparc-test-id="newStudyTitleFld"]', 'my sleepers');

  await page.waitForSelector('[osparc-test-id="newStudySubmitBtn"]')
  await page.click('[osparc-test-id="newStudySubmitBtn"]')

  await page.waitFor(2000);

  await page.waitForSelector('[osparc-test-id="runStudyBtn"]')
  await page.click('[osparc-test-id="runStudyBtn"]')

  await page.waitFor(30000);
}

async function __dashboardFilterStudiesByText(page, templateName) {
  console.log("Filtering by", templateName);

  await page.waitFor(1000)
  await page.waitFor('[osparc-test-id="studyFiltersTextFld"]')
  await page.click('[osparc-test-id="studyFiltersTextFld"]')
  await page.type('[osparc-test-id="studyFiltersTextFld"]', templateName)
  await page.keyboard.press('Enter')
  await page.waitFor(1000)
}

async function dashboardDeleteFirstStudy(page) {
  console.log("Deleting first study")

  await page.waitForSelector('[osparc-test-id="studiesTabBtn"]')
  await page.click('[osparc-test-id="studiesTabBtn"]')

  await page.waitForSelector('[osparc-test-id="userStudiesList"] > .qx-pb-listitem:nth-child(1)')
  await page.click('[osparc-test-id="userStudiesList"] > .qx-pb-listitem:nth-child(1)')

  await page.waitForSelector('[osparc-test-id="deleteStudiesBtn"]')
  await page.click('[osparc-test-id="deleteStudiesBtn"]')

  await page.waitFor(500)

  await page.waitForSelector('[osparc-test-id="confirmDeleteStudyBtn"]')
  await page.click('[osparc-test-id="confirmDeleteStudyBtn"]')
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
