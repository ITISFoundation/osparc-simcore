const utils = require("./utils")
const responses = require('./responsesQueue');

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


  await page.waitForSelector('[osparc-test-id="userMenuMainBtn"]', {
    visible: true,
    timeout: 2000
  });
  await utils.waitAndClick(page, '[osparc-test-id="userMenuMainBtn"]');
  await utils.waitAndClick(page, '[osparc-test-id="userMenuLogoutBtn"]');
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

async function dashboardEditFristStudyThumbnail(page) {
  console.log("Editing thumbnail")

  await utils.waitAndClick(page, '[osparc-test-id="studiesTabBtn"]')

  const children = await utils.getVisibleChildrenIDs(page, '[osparc-test-id="userStudiesList"]');
  if (children.length === 0) {
    console.log("Editing thumbnail: no study found")
    return
  }
  const firstChildId = '[osparc-test-id="' + children[0] + '"]'
  await utils.waitAndClick(page, firstChildId)
  await utils.waitAndClick(page, '[osparc-test-id="editStudyBtn"]')

  await page.waitForSelector('[osparc-test-id="studyDetailsEditorThumbFld"]')
  await utils.emptyField(page, '[osparc-test-id="studyDetailsEditorThumbFld"]')
  await page.click('[osparc-test-id="studyDetailsEditorThumbFld"]')
  await page.type('[osparc-test-id="studyDetailsEditorThumbFld"]', 'https://i.ytimg.com/vi/Oj3aB_wMtno/hqdefault.jpg')

  await utils.waitAndClick(page, '[osparc-test-id="studyDetailsEditorSaveBtn"]')
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
  await utils.waitAndClick(page, '[osparc-test-id="dashboardBtn"]')
}

async function dashboardOpenFirstTemplate(page, templateName) {
  // Returns true if template is found
  console.log("Creating New Study from template");

  await utils.waitAndClick(page, '[osparc-test-id="discoverTabBtn"]')

  if (templateName) {
    await __filterTemplatesByText(page, templateName);
  }

  await page.waitForSelector('[osparc-test-id="templateStudiesList"]')
  const children = await utils.getVisibleChildrenIDs(page, '[osparc-test-id="templateStudiesList"]');

  if (children.length) {
    const firstChildId = '[osparc-test-id="' + children[0] + '"]';
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

async function runStudy(page, waitFor = 0) {
  console.log("Running study");

  const responsesQueue = new responses.ResponsesQueue(page);
  responsesQueue.addResponseListener("/start");

  await utils.waitAndClick(page, '[osparc-test-id="runStudyBtn"]')

  // make sure start request was sent
  const tries = 3;
  let reqInQueue = responsesQueue.isRequestInQueue("/start");
  for (let i = 0; i < tries && reqInQueue; i++) {
    await utils.sleep(200);
    reqInQueue = responsesQueue.isRequestInQueue("/start");
  }
  if (reqInQueue) {
    console.log("Starting pipeline didn't work, pressing 'Run' again");
    await page.click('[osparc-test-id="runStudyBtn"]');
  }

  try {
    await responsesQueue.waitUntilResponse("/start");
  }
  catch (err) {
    console.error(err);
    throw (err);
  }

  console.log("Running study and waiting for", waitFor / 1000, "seconds");
  await page.waitFor(waitFor);
}

async function dashboardDeleteFirstStudy(page, studyName) {
  console.log("Deleting first study")

  await utils.waitAndClick(page, '[osparc-test-id="studiesTabBtn"]')

  if (studyName) {
    await __filterStudiesByText(page, studyName);
  }

  await page.waitForSelector('[osparc-test-id="userStudiesList"]')
  const children = await utils.getVisibleChildrenIDs(page, '[osparc-test-id="userStudiesList"]');
  if (children.length === 0) {
    console.log("Deleting first Study: no study found");
    return;
  }
  const firstChildId = '[osparc-test-id="' + children[0] + '"]';
  await utils.waitAndClick(page, firstChildId + ' > [osparc-test-id="studyItemMenuButton"]');
  await utils.waitAndClick(page, '[osparc-test-id="studyItemMenuDelete"]');
  await utils.waitAndClick(page, '[osparc-test-id="confirmDeleteStudyBtn"]');
}

async function openNode(page, pos) {
  console.log("Opening Node in position", pos);

  const children = await utils.getNodeTreeItemIDs(page);
  console.log("children", children);
  if (children.length < pos + 1) {
    console.log("Node tree items not found");
    return null;
  }
  const nodeWidgetId = children[pos];
  const childId = '[osparc-test-id="' + nodeWidgetId + '"]';
  await utils.waitAndClick(page, childId);
  await utils.waitAndClick(page, '[osparc-test-id="openServiceBtn"]');

  const nodeId = nodeWidgetId.replace("nodeTreeItem_", "");
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

async function maximizeIFrame(page) {
  console.log("Maximizing iFrame");

  await utils.waitAndClick(page, '[osparc-test-id="maximizeBtn"]')
}

async function openNodeFiles(page) {
  console.log("Opening Data produced by Node");

  await utils.waitAndClick(page, '[osparc-test-id="nodeViewFilesBtn"]')
}

async function checkDataProducedByNode(page, nFiles = 1) {
  console.log("checking Data produced by Node. Expecting", nFiles, "file(s)");
  const tries = 3;
  let children = [];
  const minTime = 1000; // wait a bit longer for fetching the files
  for (let i = 0; i < tries && children.length === 0; i++) {
    await page.waitFor(minTime * (i + 1));
    await page.waitForSelector('[osparc-test-id="fileTreeItem_NodeFiles"]');
    children = await utils.getFileTreeItemIDs(page, "NodeFiles");
    console.log(i + 1, 'try: ', children);
  }
  const nFolders = 3;
  if (children.length < (nFolders + nFiles)) { // 4 = location + study + node + file
    throw ("Expected files not found");
  }

  const lastChildId = '[osparc-test-id="' + children.pop() + '"]';
  await utils.waitAndClick(page, lastChildId);
  await utils.waitAndClick(page, '[osparc-test-id="nodeDataManagerCloseBtn"]');
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

async function clickRetrieve(page) {
  console.log("Opening Data produced by Node");

  await utils.waitAndClick(page, '[osparc-test-id="nodeViewRetrieveBtn"]')
}

async function clickRestart(page) {
  console.log("Opening Data produced by Node");

  await utils.waitAndClick(page, '[osparc-test-id="nodeViewRetrieveBtn"]')
}


module.exports = {
  register,
  logIn,
  logOut,
  dashboardAbout,
  dashboardPreferences,
  dashboardDiscoverBrowser,
  dashboardDataBrowser,
  dashboardStudyBrowser,
  dashboardEditFristStudyThumbnail,
  dashboardNewStudy,
  dashboardOpenFirstTemplate,
  runStudy,
  dashboardDeleteFirstStudy,
  toDashboard,
  openNode,
  openLastNode,
  restoreIFrame,
  maximizeIFrame,
  openNodeFiles,
  checkDataProducedByNode,
  downloadSelectedFile,
  clickRetrieve,
  clickRestart,
}
