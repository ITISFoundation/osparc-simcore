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

async function ignoreNewRelease(page) {
  const id = '[osparc-test-id=newReleaseCloseBtn]';
  await page.waitForSelector(id, {
    timeout: 5000
  })
    .then(() => page.click(id))
    .catch(() => console.log("newReleaseClose button not found"));
}

async function closeQuickStart(page) {
  const id = '[osparc-test-id=quickStartWindowCloseBtn]';
  await page.waitForSelector(id, {
    timeout: 5000
  })
    .then(() => page.click(id))
    .catch(() => console.log("Quick Start window not found"));
}

async function toLogInPage(page) {
  const id = '[osparc-test-id=toLogInPage]';
  await page.waitForSelector(id, {
    timeout: 2000
  })
    .then(() => page.click(id))
    .catch(() => console.log("toLogInPage button not found"));
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
  const elementExists = await page.$('[osparc-test-id="userMenuBtn"]');
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

  await utils.waitAndClick(page, '[osparc-test-id="userMenuBtn"]');
  await utils.waitAndClick(page, '[osparc-test-id="userMenuLogoutBtn"]');
}

async function dashboardAbout(page) {
  console.log("Showing About");

  await utils.waitAndClick(page, '[osparc-test-id="userMenuBtn"]');
  await utils.waitAndClick(page, '[osparc-test-id="userMenuAboutBtn"]');
  await utils.waitAndClick(page, '[osparc-test-id="aboutWindowCloseBtn"]');
}

async function dashboardPreferences(page) {
  console.log("Navigating through Preferences");

  await utils.waitAndClick(page, '[osparc-test-id="userMenuBtn"]');
  await utils.waitAndClick(page, '[osparc-test-id="userMenuPreferencesBtn"]');
  await utils.waitAndClick(page, '[osparc-test-id="preferencesProfileTabBtn"]');
  await utils.waitAndClick(page, '[osparc-test-id="preferencesSecurityTabBtn"]');
  await utils.waitAndClick(page, '[osparc-test-id="preferencesWindowCloseBtn"]');
}

async function dashboardStudiesBrowser(page) {
  console.log("Navigating through Studies");
  await utils.waitAndClick(page, '[osparc-test-id="studiesTabBtn"]')
}

async function __dashboardTemplatesBrowser(page) {
  console.log("Navigating through Templates");
  await utils.waitAndClick(page, '[osparc-test-id="templatesTabBtn"]');
}

async function __dashboardServicesBrowser(page) {
  console.log("Navigating through Services");
  await utils.waitAndClick(page, '[osparc-test-id="servicesTabBtn"]');
}

async function dashboardNewTIPlan(page) {
  console.log("Creating New Plan");

  await dashboardStudiesBrowser(page);
  await utils.waitAndClick(page, '[osparc-test-id="newStudyBtn"]');
  await utils.waitAndClick(page, '[osparc-test-id="newTIPlanButton"]');
}

async function dashboardStartSim4LifeLite(page) {
  console.log("Start Sim4Lite from + button");

  await dashboardStudiesBrowser(page);
  await utils.waitAndClick(page, '[osparc-test-id="startS4LButton"]');
}

async function toDashboard(page) {
  console.log("To Dashboard");

  await utils.waitAndClick(page, '[osparc-test-id="dashboardBtn"]');
  await utils.waitAndClick(page, '[osparc-test-id="confirmDashboardBtn"]');
}

async function dashboardOpenFirstTemplate(page, templateName) {
  // wait for All Templates
  await utils.sleep(10000);

  // Returns true if template is found
  console.log("Creating New Study from template");

  await utils.takeScreenshot(page, "click on templates tab");
  await __dashboardTemplatesBrowser(page);
  await utils.takeScreenshot(page, "clicked on templates tab");

  if (templateName) {
    // Show flat list
    await utils.waitAndClick(page, '[osparc-test-id="groupByButton"]', 1000);
    await utils.sleep(1000);
    await utils.waitAndClick(page, '[osparc-test-id="groupByNone"]', 1000);
    await utils.sleep(1000);

    await utils.takeScreenshot(page, "type filter text");
    await __filterTemplatesByText(page, templateName);
    await utils.takeScreenshot(page, "typed filter text");
  }

  await page.waitForSelector('[osparc-test-id="templatesList"]');
  const children = await utils.getVisibleChildrenIDs(page, '[osparc-test-id="templatesList"]');

  if (children.length) {
    const firstChildId = '[osparc-test-id="' + children[0] + '"]';
    await utils.waitAndClick(page, firstChildId);
    await __openResource(page);
    return true;
  }
  console.log("Creating New Study from template: no template found");
  return false;
}

async function dashboardOpenService(page, serviceName) {
  await utils.sleep(5000);

  // Returns true if template is found
  console.log("Creating New Study from service");

  await __dashboardServicesBrowser(page);

  if (serviceName) {
    await __filterServicesByText(page, serviceName);
  }

  await page.waitForSelector('[osparc-test-id="servicesList"]')
  const children = await utils.getVisibleChildrenIDs(page, '[osparc-test-id="servicesList"]');
  if (children.length) {
    let idx = 0;
    for (let i = 0; i < children.length; i++) {
      const childId = '[osparc-test-id="' + children[i] + '"]';
      const cardLabel = await utils.getDashboardCardLabel(page, childId);
      if (cardLabel === serviceName) {
        idx = i;
        break;
      }
    }
    const firstChildId = '[osparc-test-id="' + children[idx] + '"]';
    await utils.waitAndClick(page, firstChildId);
    await __openResource(page);
    return true;
  }
  console.log("Creating New Study from service: no service found");
  return false;
}

async function __openResource(page) {
  await utils.waitAndClick(page, '[osparc-test-id="openResource"]');

  // Under some circumstances, users might need to also go through the resource selection window
  const id = '[osparc-test-id=openWithResources]';
  await page.waitForSelector(id, {
    timeout: 5000
  })
    .then(() => page.click(id))
    .catch(() => console.log("Accept Cookies button not found"));
}

async function __filterStudiesByText(page, studyName) {
  await dashboardStudiesBrowser(page);
  await __typeInSearchBarFilter(page, "study", studyName);
}

async function __filterTemplatesByText(page, templateName) {
  await __dashboardTemplatesBrowser(page);
  await __typeInSearchBarFilter(page, "template", templateName);
}

async function __filterServicesByText(page, serviceName) {
  await __dashboardServicesBrowser(page);
  await __typeInSearchBarFilter(page, "service", serviceName);
}

async function __typeInSearchBarFilter(page, resource, text) {
  const fieldSelector = '[osparc-test-id="searchBarFilter-textField-' + resource + '"]';
  await __typeInFilter(page, fieldSelector, text);
}

async function __typeInFilter(page, selector, text) {
  console.log("Filtering by", text);

  await utils.waitAndClick(page, selector);
  await utils.clearInput(page, selector);
  await page.type(selector, text);
  await page.keyboard.press('Enter');
}

async function showLogger(page, show = true) {
  const isVisible = await utils.isElementVisible(page, '[osparc-test-id="logsViewer"]');

  if (show !== isVisible) {
    await utils.clickLoggerTitle(page);
  }
}

async function findLogMessage(page, text) {
  console.log("Finding Log Message containing '" + text + "'");
  await this.showLogger(page, true);

  await utils.waitAndClick(page, '[osparc-test-id="logsFilterField"]');
  await utils.clearInput(page, '[osparc-test-id="logsFilterField"]');
  await utils.takeScreenshot(page, 'findLogMessage_' + text + "_before");
  await page.type('[osparc-test-id="logsFilterField"]', text);
  await utils.sleep(2000);

  const found1 = await page.evaluate((text) => window.find(text), text);
  await utils.takeScreenshot(page, 'findLogMessage_' + text + "_after");
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
    console.error("Error: running study", err);
    throw (err);
  }
}

async function deleteFirstStudy(page, studyName) {
  console.log("Deleting first study")

  await dashboardStudiesBrowser(page);

  if (studyName) {
    await __filterStudiesByText(page, studyName);
  }

  await page.waitForSelector('[osparc-test-id="studiesList"]')
  const childrenIDs = await utils.getVisibleChildrenIDs(page, '[osparc-test-id="studiesList"]');

  const studyIDs = childrenIDs.filter(childId => childId.includes("studyBrowserListItem_"));
  if (studyIDs.length === 0) {
    console.log("Deleting first Study: no study found");
    return false;
  }

  const studyCardId = studyIDs[0];
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
  const childId = '[osparc-test-key="' + nodeId + '"]';
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

  await utils.waitAndClick(page, '[osparc-test-id="nodeFilesBtn"]');
}

async function openNodeFilesAppMode(page) {
  console.log("Opening Data produced by Node App Mode");

  await utils.waitAndClick(page, '[osparc-test-id="outputsBtn"]');
  await utils.waitAndClick(page, '[osparc-test-id="nodeFilesBtn"]');
}

async function checkDataProducedByNode(page, nFiles = 1) {
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
    console.error("Error: downloading Selected File", err);
    throw (err);
  }
}


module.exports = {
  acceptCookies,
  ignoreNewRelease,
  closeQuickStart,
  toLogInPage,
  register,
  logIn,
  logOut,
  dashboardAbout,
  dashboardStudiesBrowser,
  dashboardPreferences,
  dashboardNewTIPlan,
  dashboardStartSim4LifeLite,
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
  openNodeFilesAppMode,
  checkDataProducedByNode,
  downloadSelectedFile
}
