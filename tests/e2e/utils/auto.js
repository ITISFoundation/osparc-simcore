const utils = require("./utils")
const responses = require('./responsesQueue');
require('log-timestamp');

async function acceptCookies(page) {
  const id = '[osparc-test-id=acceptCookiesBtn]';
  await page.waitForSelector(id, {
    timeout: 5000
  })
    .then(() => page.click(id))
    .catch(() => console.log("Accept Cookies button not found"));
}

async function register(page, user, pass) {
  await utils.waitAndClick(page, '[osparc-test-id="loginCreateAccountBtn"]');

  console.log("Registering:", user);
  await page.waitForSelector('[osparc-test-id="registrationEmailFld"]');
  await page.type('[osparc-test-id="registrationEmailFld"]', user);
  await page.type('[osparc-test-id="registrationPass1Fld"]', pass);
  await page.type('[osparc-test-id="registrationPass2Fld"]', pass);
  await utils.waitAndClick(page, '[osparc-test-id="registrationSubmitBtn"]');
}

async function logIn(page, user, pass) {
  // user might be already logged in
  const elementExists = await page.$('[osparc-test-id="userMenuMainBtn"]');
  if (elementExists !== null) {
    return;
  }

  // NOTE: since environ WEBSERVER_LOGIN_REGISTRATION_CONFIRMATION_REQUIRED=0, the
  // backend automatically creates session after registration is submitted
  console.log("Logging in:", user);
  await page.waitForSelector('[osparc-test-id="loginUserEmailFld"]', {
    visible: true,
    timeout: 10000
  });
  await page.type('[osparc-test-id="loginUserEmailFld"]', user);
  await page.waitForSelector('[osparc-test-id="loginPasswordFld"]');
  await page.type('[osparc-test-id="loginPasswordFld"]', pass);
  await utils.waitAndClick(page, '[osparc-test-id="loginSubmitBtn"]');
}

async function logOut(page) {
  console.log("Logging out");

  await utils.waitAndClick(page, '[osparc-test-id="userMenuMainBtn"]');
  await utils.waitAndClick(page, '[osparc-test-id="userMenuLogoutBtn"]');
  await page.waitForSelector('[osparc-test-id="loginSubmitBtn"]');
}

async function dashboardAbout(page) {
  console.log("Showing About");

  await utils.waitAndClick(page, '[osparc-test-id="userMenuMainBtn"]');
  await utils.waitAndClick(page, '[osparc-test-id="userMenuAboutBtn"]');
  await utils.waitAndClick(page, '[osparc-test-id="aboutWindowCloseBtn"]');
}

async function dashboardPreferences(page) {
  console.log("Navigating through Preferences");

  await utils.waitAndClick(page, '[osparc-test-id="userMenuMainBtn"]');
  await utils.waitAndClick(page, '[osparc-test-id="userMenuPreferencesBtn"]');
  await utils.waitAndClick(page, '[osparc-test-id="preferencesProfileTabBtn"]');
  await utils.waitAndClick(page, '[osparc-test-id="preferencesSecurityTabBtn"]');
  await utils.waitAndClick(page, '[osparc-test-id="preferencesExperimentalTabBtn"]');
  await utils.waitAndClick(page, '[osparc-test-id="preferencesWindowCloseBtn"]');
}

async function dashboardDiscoverBrowser(page) {
  console.log("Navigating through Templates and Services");
  await utils.waitAndClick('[osparc-test-id="discoverTabBtn"]');
}

async function dashboardDataBrowser(page) {
  console.log("Navigating through Data");

  await utils.waitAndClick(page, '[osparc-test-id="dataTabBtn"]')
  // expand first location
  await utils.waitAndClick(page, '.qx-no-border > div > div > div > div:nth-child(2) > div:nth-child(1)')
  // expand first study
  await utils.waitAndClick(page, '.qx-no-border > div > div > div > div:nth-child(3) > div:nth-child(1)')
}

async function dashboardStudyBrowser(page) {
  console.log("Navigating through Templates");

  await utils.waitAndClick(page, '[osparc-test-id="studiesTabBtn"]')

  const children = await utils.getVisibleChildrenIDs(page, '[osparc-test-id="templateStudiesList"]');
  if (children.length === 0) {
    console.log("Editing thumbnail: no study found")
    return
  }
  for (let i = 0; i < children.length; i++) {
    const childId = '[osparc-test-id="' + children[i] + '"]'
    await utils.waitAndClick(page, childId);
  }
}

async function dashboardNewStudy(page) {
  console.log("Creating New Study");

  await utils.waitAndClick(page, '[osparc-test-id="studiesTabBtn"]')
  await utils.waitAndClick(page, '[osparc-test-id="newStudyBtn"]');

  await page.waitForSelector('[osparc-test-id="newStudyTitleFld"]');
  await page.type('[osparc-test-id="newStudyTitleFld"]', 'puppeteering study');
  await page.type('[osparc-test-id="newStudyDescFld"]', 'this is puppeteer creating a new study');

  await page.click('[osparc-test-id="newStudySubmitBtn"]');
}

async function toDashboard(page) {
  console.log("To Dashboard");

  await utils.waitAndClick(page, '[osparc-test-id="dashboardBtn"]');
  await utils.waitAndClick(page, '[osparc-test-id="confirmDashboardBtn"]');
}

async function waitForAllTemplates(page) {
  await page.waitForSelector('[osparc-test-id="templateStudiesList"]');
  let loadingTemplatesCardVisible = true;
  while(loadingTemplatesCardVisible) {
    const childrenIDs = await utils.getVisibleChildrenIDs(page, '[osparc-test-id="templateStudiesList"]');
    loadingTemplatesCardVisible = childrenIDs.some(childrenID => childrenID.includes("templatesLoading"));
  }
}

async function dashboardOpenFirstTemplate(page, templateName) {
  // Returns true if template is found
  console.log("Creating New Study from template");

  await utils.waitAndClick(page, '[osparc-test-id="discoverTabBtn"]')

  if (templateName) {
    await __filterTemplatesByText(page, templateName);
  }

  await this.waitForAllTemplates(page);

  await page.waitForSelector('[osparc-test-id="templateStudiesList"]');
  const children = await utils.getVisibleChildrenIDs(page, '[osparc-test-id="templateStudiesList"]');

  if (children.length) {
    const firstChildId = '[osparc-test-id="' + children[0] + '"]';
    await utils.waitAndClick(page, firstChildId);
    return true;
  }
  console.log("Creating New Study from template: no template found");
  return false;
}

async function dashboardOpenService(page, serviceName) {
  // Returns true if template is found
  console.log("Creating New Study from template");

  await utils.waitAndClick(page, '[osparc-test-id="discoverTabBtn"]')

  if (serviceName) {
    await __filterTemplatesByText(page, serviceName);
  }

  await page.waitForSelector('[osparc-test-id="servicesList"]')
  const children = await utils.getVisibleChildrenIDs(page, '[osparc-test-id="servicesList"]');
  if (children.length) {
    let idx = 0;
    for (let i=0; i<children.length; i++) {
      const childId = '[osparc-test-id="' + children[i] + '"]';
      const cardLabel = await utils.getDashboardCardLabel(page, childId);
      if (cardLabel === serviceName) {
        idx = i;
        break;
      }
    }
    const firstChildId = '[osparc-test-id="' + children[idx] + '"]';
    await utils.waitAndClick(page, firstChildId);
    return true;
  }
  console.log("Creating New Study from template: no template found");
  return false;
}

async function __filterStudiesByText(page, studyName) {
  console.log("Filtering by", studyName);

  await utils.waitAndClick(page, '[osparc-test-id="sideSearchFiltersTextFld"]')
  await utils.clearInput(page, '[osparc-test-id="sideSearchFiltersTextFld"]')
  await page.type('[osparc-test-id="sideSearchFiltersTextFld"]', studyName)
  await page.keyboard.press('Enter')
}

async function __filterTemplatesByText(page, templateName) {
  console.log("Filtering by", templateName);

  await utils.waitAndClick(page, '[osparc-test-id="sideSearchFiltersTextFld"]')
  await utils.clearInput(page, '[osparc-test-id="sideSearchFiltersTextFld"]')
  await page.type('[osparc-test-id="sideSearchFiltersTextFld"]', templateName)
  await page.keyboard.press('Enter')
}

async function showLogger(page, show = true) {
  const isVisible = await utils.isElementVisible(page, '[osparc-test-id="logsViewer"]');

  if (show !== isVisible) {
    await utils.clickLoggerTitle(page);
  }
}

async function findLogMessage(page, text) {
  console.log("Finding Log Message");
  await this.showLogger(page, true);

  await utils.waitAndClick(page, '[osparc-test-id="logsFilterField"]');
  await utils.clearInput(page, '[osparc-test-id="logsFilterField"]');
  await page.type('[osparc-test-id="logsFilterField"]', text);

  const found1 = await page.evaluate((text) => window.find(text), text);
  await utils.takeScreenshot(page, 'find_' + text);
  return found1;
}

async function runStudy(page) {
  console.log("Running study");

  const responsesQueue = new responses.ResponsesQueue(page);
  responsesQueue.addResponseListener(":start");

  await utils.waitAndClick(page, '[osparc-test-id="runStudyBtn"]')

  // make sure start request was sent
  const tries = 3;
  let reqInQueue = responsesQueue.isRequestInQueue(":start");
  for (let i = 0; i < tries && reqInQueue; i++) {
    await utils.sleep(200);
    reqInQueue = responsesQueue.isRequestInQueue(":start");
  }
  if (reqInQueue) {
    console.log("Starting pipeline didn't work, pressing 'Run' again");
    await page.click('[osparc-test-id="runStudyBtn"]');
  }

  try {
    await responsesQueue.waitUntilResponse(":start");
  }
  catch (err) {
    console.error(err);
    throw (err);
  }
}

async function deleteFirstStudy(page, studyName) {
  console.log("Deleting first study")

  await utils.waitAndClick(page, '[osparc-test-id="studiesTabBtn"]')

  if (studyName) {
    await __filterStudiesByText(page, studyName);
  }

  await page.waitForSelector('[osparc-test-id="userStudiesList"]')
  const children = await utils.getVisibleChildrenIDs(page, '[osparc-test-id="userStudiesList"]');

  // filter out the cards that are not studies
  [
    "newStudyBtn",
    "studiesLoading"
  ].forEach(notAStudy => {
    const idx = children.indexOf(notAStudy);
    if (idx > -1) {
      children.splice(idx, 1);
    }
  });
  if (children.length === 0) {
    console.log("Deleting first Study: no study found");
    return false;
  }

  const studyCardId = children[0];
  const firstChildId = '[osparc-test-id="' + studyCardId + '"]';
  const studyCardStyle = await utils.getStyle(page, firstChildId);
  if (studyCardStyle.cursor === "not-allowed") {
    return false;
  }
  await utils.waitAndClick(page, firstChildId + ' > [osparc-test-id="studyItemMenuButton"]');
  await utils.waitAndClick(page, '[osparc-test-id="studyItemMenuDelete"]');
  await utils.waitAndClick(page, '[osparc-test-id="confirmDeleteStudyBtn"]');
  return true;
}

async function openNode(page, pos) {
  console.log("Opening Node in position", pos);

  const children = await utils.getNodeTreeItemIDs(page);
  console.log("children", children);
  if (pos >= children.length) {
    console.log("Node tree items not found");
    return null;
  }

  const nodeId = children[pos];
  const childId = '[osparc-test-more="' + nodeId + '"]';
  await utils.waitAndClick(page, childId);

  return nodeId;
}

async function openLastNode(page) {
  console.log("Opening Last Node");

  const children = await utils.getNodeTreeItemIDs(page);
  if (children.length < 1) {
    console.log("Node tree items not found");
    return;
  }
  this.openNode(page, children.length - 1);
}

async function restoreIFrame(page) {
  console.log("Restoring iFrame");

  await utils.waitAndClick(page, '[osparc-test-id="restoreBtn"]')
}

async function openNodeFiles(page) {
  console.log("Opening Data produced by Node");

  await utils.waitAndClick(page, '[osparc-test-id="outputsTabButton"]');
  await utils.waitAndClick(page, '[osparc-test-id="nodeOutputFilesBtn"]');
}

async function checkDataProducedByNode(page, nFiles = 1, itemSuffix = 'NodeFiles') {
  console.log("checking Data produced by Node. Expecting", nFiles, "file(s)");
  const iconsContent = await page.waitForSelector('[osparc-test-id="FolderViewerIconsContent"]', {
    timeout: 5000
  });
  const items = await iconsContent.$$('[osparc-test-id="FolderViewerItem"]');
  await utils.waitAndClick(page, '[osparc-test-id="nodeDataManagerCloseBtn"]');
  return nFiles === items.length;
}

async function downloadSelectedFile(page) {
  console.log("downloading Data produced by Node")

  await utils.waitAndClick(page, '[osparc-test-id="filesTreeDownloadBtn"]')

  try {
    const value = await utils.waitForValidOutputFile(page)
    console.log("valid output file value", value)
  }
  catch (err) {
    console.error(err);
    throw (err);
  }
}


module.exports = {
  acceptCookies,
  register,
  logIn,
  logOut,
  dashboardAbout,
  dashboardPreferences,
  dashboardDiscoverBrowser,
  dashboardDataBrowser,
  dashboardStudyBrowser,
  dashboardNewStudy,
  waitForAllTemplates,
  dashboardOpenFirstTemplate,
  dashboardOpenService,
  showLogger,
  findLogMessage,
  runStudy,
  deleteFirstStudy,
  toDashboard,
  openNode,
  openLastNode,
  restoreIFrame,
  openNodeFiles,
  checkDataProducedByNode,
  downloadSelectedFile
}
