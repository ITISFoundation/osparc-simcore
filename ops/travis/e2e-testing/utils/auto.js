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

  await page.waitForSelector('[osparc-test-id="newStudyBtn"]');
  await page.click('[osparc-test-id="newStudyBtn"]');

  await page.waitForSelector('[osparc-test-id="newStudyTitleFld"]');
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

  await page.waitForSelector('[osparc-test-id="templateStudiesList"]')
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

  await page.waitForSelector('[osparc-test-id="runStudyBtn"]')
  await page.click('[osparc-test-id="runStudyBtn"]')
}

async function __dashboardFilterStudiesByText(page, templateName) {
  console.log("Filtering by", templateName);

  await page.waitForSelector('[osparc-test-id="studyFiltersTextFld"]')
  await page.click('[osparc-test-id="studyFiltersTextFld"]')
  await page.type('[osparc-test-id="studyFiltersTextFld"]', templateName)
  await page.keyboard.press('Enter')
}

async function dashboardDeleteFirstStudy(page) {
  console.log("Deleting first study")

  await page.waitForSelector('[osparc-test-id="studiesTabBtn"]')
  await page.click('[osparc-test-id="studiesTabBtn"]')

  await page.waitForSelector('[osparc-test-id="userStudiesList"] > .qx-pb-listitem:nth-child(1)')
  await page.click('[osparc-test-id="userStudiesList"] > .qx-pb-listitem:nth-child(1)')

  await page.waitForSelector('[osparc-test-id="deleteStudiesBtn"]')
  await page.click('[osparc-test-id="deleteStudiesBtn"]')

  await page.waitForSelector('[osparc-test-id="confirmDeleteStudyBtn"]')
  await page.click('[osparc-test-id="confirmDeleteStudyBtn"]')
}

async function openNode(page, pos) {
  console.log("Opening Node in position", pos);

  const children = await utils.getNodeTreeItemIDs(page);
  console.log("children", children);
  if (children.length < pos+1) {
    console.log("Node tree items not found");
    return;
  }
  const childId = '[osparc-test-id="' + children[pos] + '"]';
  await page.waitForSelector(childId);
  await page.click(childId);

  await page.waitForSelector('[osparc-test-id="openServiceBtn"]');
  await page.click('[osparc-test-id="openServiceBtn"]');
}

async function openLastNode(page) {
  console.log("Opening Last Node");

  const children = await utils.getNodeTreeItemIDs(page);
  if (children.length < 1) {
    console.log("Node tree items not found");
    return;
  }
  this.openNode(page, children.length-1);
}

async function checkDataProducedByNode(page) {
  console.log("checking Data produced by Node")

  await page.waitForSelector('[osparc-test-id="nodeViewFilesBtn"]')
  await page.click('[osparc-test-id="nodeViewFilesBtn"]')

  await utils.waitForResponse(page, "storage/locations/0/files/metadata?uuid_filter=")

  await page.waitForSelector('[osparc-test-id="fileTreeItem_NodeFiles"]')
  const children = await utils.getFileTreeItemIDs(page, "NodeFiles");
  console.log(children);
  if (children.length < 4) { // 4 = location + study + node + file
    throw("file items not found");
  }

  const lastChildId = '[osparc-test-id="' + children.pop() + '"]';
  await page.waitForSelector(lastChildId)
  await page.click(lastChildId)

  downloadSelectedFile(page)

  await page.waitForSelector('[osparc-test-id="nodeDataManagerCloseBtn"]')
  await page.click('[osparc-test-id="nodeDataManagerCloseBtn"]')
}

async function downloadSelectedFile(page) {
  await page.waitForSelector('[osparc-test-id="filesTreeDownloadBtn"]')
  await page.click('[osparc-test-id="filesTreeDownloadBtn"]')

  await utils.waitForValidSleeperOutputFile(page)
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
  openNode,
  openLastNode,
  checkDataProducedByNode,
  downloadSelectedFile,
}
