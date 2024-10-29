const pathLib = require('path');
const URL = require('url').URL;

const SCREENSHOTS_DIR = "../screenshots/";
const DEFAULT_TIMEOUT = 60000;

function parseCommandLineArguments(args) {
  // node $tutorial.js
  // url
  // [--user user]
  // [--pass pass]
  // [--n_users nUsers]
  // [--user_prefix userPrefix]
  // [--user_suffix userSuffix]
  // [--start_timeout startTimeout]
  // [--basicauth_user basicauthUsername]
  // [--basicauth_pass basicauthPassword]
  // [--demo]

  if (args.length < 1) {
    console.log('Minimum arguments expected: $tutorial.js url');
    process.exit(1);
  }

  const url = args[0];

  let user = null;
  const userIdx = args.indexOf('--user');
  if (userIdx > -1) {
    user = args[userIdx + 1];
  }

  let pass = null;
  const passIdx = args.indexOf('--pass');
  if (passIdx > -1) {
    pass = args[passIdx + 1];
  }

  let nUsers = null;
  const nUsersIdx = args.indexOf('--n_users');
  if (nUsersIdx > -1) {
    nUsers = args[nUsersIdx + 1];
  }

  let userPrefix = null;
  const userPrefixIdx = args.indexOf('--user_prefix');
  if (userPrefixIdx > -1) {
    userPrefix = args[userPrefixIdx + 1];
  }

  let userSuffix = null;
  const userSuffixIdx = args.indexOf('--user_suffix');
  if (userSuffixIdx > -1) {
    userSuffix = args[userSuffixIdx + 1];
  }

  let startTimeout = DEFAULT_TIMEOUT;
  const startTimeoutIdx = args.indexOf('--start_timeout');
  if (startTimeoutIdx > -1) {
    startTimeout = args[startTimeoutIdx + 1];
  }

  let basicauthUsername = "";
  const basicauthUsernameIdx = args.indexOf('--basicauth_user');
  if (basicauthUsernameIdx > -1) {
    basicauthUsername = args[basicauthUsernameIdx + 1];
  }

  let basicauthPassword = "";
  const basicauthPasswordIdx = args.indexOf('--basicauth_pass');
  if (basicauthPasswordIdx > -1) {
    basicauthPassword = args[basicauthPasswordIdx + 1];
  }
  const enableDemoMode = (args.indexOf("--demo") > -1);
  const serviceNameIdx = (args.indexOf("--service_name"));
  let serviceName = "";
  if (serviceNameIdx > -1) {
    serviceName = args[serviceNameIdx + 1];
  }


  let newUser = false;
  if (pass === null) {
    const newCredentials = getUserAndPass(args);
    user = newCredentials.user;
    pass = newCredentials.pass;
    newUser = true;
  }

  return {
    url,
    user,
    pass,
    newUser,
    nUsers,
    userPrefix,
    userSuffix,
    startTimeout,
    basicauthUsername,
    basicauthPassword,
    enableDemoMode,
    serviceName
  }
}

function parseCommandLineArgumentsAnonymous(args) {
  // node $template.js
  // url_prefix
  // template_uuid
  // start_timeout
  // [--basicauth_user basicauthUsername]
  // [--basicauth_pass basicauthPassword]
  // [--demo]

  if (args.length < 3) {
    console.log('Minimum arguments expected: $template.js url_prefix template_uuid, start_timeout');
    process.exit(1);
  }

  const urlPrefix = args[0];
  const templateUuid = args[1];
  const startTimeout = args[2];

  let basicauthUsername = "";
  const basicauthUsernameIdx = args.indexOf('--basicauth_user');
  if (basicauthUsernameIdx > -1) {
    basicauthUsername = args[basicauthUsernameIdx + 1];
  }

  let basicauthPassword = "";
  const basicauthPasswordIdx = args.indexOf('--basicauth_pass');
  if (basicauthPasswordIdx > -1) {
    basicauthPassword = args[basicauthPasswordIdx + 1];
  }

  const enableDemoMode = args.includes("--demo");

  return {
    urlPrefix,
    templateUuid,
    startTimeout,
    basicauthUsername,
    basicauthPassword,
    enableDemoMode
  }
}

function parseCommandLineArgumentsStudyDispatcherParams(args) {
  // [url] [download_link] [file_size] [--demo]

  if (args.length < 4) {
    console.log('More arguments expected: [url] [download_link] [file_size] [--start_timeout timeout] [--demo]');
    process.exit(1);
  }

  const urlPrefix = args[0];
  const params = {};
  params["download_link"] = args[1];
  params["file_size"] = args[2];
  const startTimeout = args[2];
  const enableDemoMode = args.includes("--demo");

  return {
    urlPrefix,
    params,
    startTimeout,
    enableDemoMode
  }
}

function getUserAndPass(args) {
  const userPass = {
    user: null,
    pass: null,
    newUser: true
  };
  if (args && args.length > 2) {
    userPass.user = args[1];
    userPass.pass = args[2];
    userPass.newUser = false;
  }
  else {
    const rand = __getRandUserAndPass();
    userPass.user = rand.user;
    userPass.pass = rand.pass;
  }
  return userPass;
}


function generateString(length) {
  const characters = "abcdefghijklmnopqrstuvwxyz0123456789";
  let result = "";
  const charactersLength = characters.length;
  for (let i=0; i<length; i++) {
    result += characters.charAt(Math.floor(Math.random() * charactersLength));
  }
  return result;
}

function __getRandUserAndPass() {
  const randUser = generateString(6);
  const user = 'puppeteer_' + randUser + '@itis.testing';
  const pass = generateString(12);
  return {
    user,
    pass
  }
}

function getDomain(url) {
  url = url.replace("http://", "");
  url = url.replace("https://", "");
  url = url.substr(0, url.indexOf("/"));
  return url;
}

async function getChildrenElements(element) {
  const children = await element.$$(':scope > *');
  return children;
}

async function getChildrenElementsBySelector(page, selector) {
  const parent = await page.$(selector);
  const children = await getChildrenElements(parent);
  return children;
}

async function getNodeTreeItemIDs(page) {
  const childrenIDs = await page.evaluate((selector) => {
    const children = [];
    const nodeTreeItems = document.querySelectorAll(selector);
    nodeTreeItems.forEach(nodeTreeItem => {
      const nodeId = nodeTreeItem.getAttribute("osparc-test-key")
      if (nodeId !== "root") {
        children.push(nodeId);
      }
    });
    return children;
  }, '[osparc-test-id="nodeTreeItem"]');
  return childrenIDs;
}

async function getFileTreeItemIDs(page, rootName) {
  const childrenIDs = await page.evaluate((selector) => {
    const children = [];
    const treeRoot = document.querySelector(selector);
    if (treeRoot.parentElement) {
      const tree = treeRoot.parentElement;
      for (let i = 1; i < tree.children.length; i++) {
        const child = tree.children[i];
        children.push(child.getAttribute("osparc-test-id"));
      }
    }
    return children;
  }, '[osparc-test-id="fileTreeItem_' + rootName + '"]');
  return childrenIDs;
}

async function getVisibleChildrenIDs(page, parentSelector) {
  const childrenIDs = await page.evaluate((selector) => {
    const parentNode = document.querySelector(selector);
    const children = [];
    for (let i = 0; i < parentNode.children.length; i++) {
      const child = parentNode.children[i];
      const style = window.getComputedStyle(child);
      if (style.display !== 'none') {
        children.push(child.getAttribute("osparc-test-id"));
      }
    }
    return children;
  }, parentSelector);
  return childrenIDs;
}

async function getDashboardCardLabel(page, selector) {
  const cardLabel = await page.evaluate((selector) => {
    let label = null;
    const card = document.querySelector(selector);
    if (card && card.children && card.children.length) {
      if (card.children[0].children && card.children[0].children.length > 1) {
        label = card.children[0].children[1].innerText;
      }
    }
    return label;
  }, selector);
  return cardLabel;
}

async function getStyle(page, selector) {
  const style = await page.evaluate((selector) => {
    const node = document.querySelector(selector);
    return JSON.parse(JSON.stringify(getComputedStyle(node)));
  }, selector);
  return style;
}

async function fetchReq(endpoint) {
  const responseEnv = await page.evaluate(
    // NOTE: without the following comment it fails here with some weird message
    /* istanbul ignore next */
    async (url, apiVersion, endpoint) => {
      const response = await fetch(url + apiVersion + endpoint);
      return await response.json();
    }, url, apiVersion, endpoint);
  return responseEnv;
}

async function __getHost(page) {
  const getHost = () => {
    // return window.location.protocol + "//" + window.location.hostname;
    return window.location.href;
  }
  const host = await page.evaluate(getHost);
  return host;
}

async function makeRequest(page, endpoint, apiVersion = "v0") {
  const host = await __getHost(page);
  // https://github.com/Netflix/pollyjs/issues/149#issuecomment-481108446
  await page.setBypassCSP(true);
  const resp = await page.evaluate(async (host, endpoint, apiVersion) => {
    const url = host + apiVersion + endpoint;
    console.log("makeRequest", url);
    const resp = await fetch(url);

    if (!resp.ok) {
      if (resp.statusText === 503) {
        console.log("SERVICE UNAVAILABLE");
      }
      console.log("RESP NOT OK", JSON.stringify(resp));
      return null;
    }

    try {
      // clone() the response. Otherwise, if the json() fails,
      // the response will be consumed and it can't be textified in the catch
      const jsonResp = await resp.clone().json();
      return jsonResp["data"];
    }
    catch(error) {
      console.log("-- No JSON in response --");
      console.log("Error", error);
      console.log("Request:", url);
      console.log("Response headers:", resp.headers);
      console.log("Response:", await resp.text());
    }
    return resp;
  }, host, endpoint, apiVersion);
  return resp;
}

async function emptyField(page, selector) {
  await page.evaluate((selector) => document.querySelector(selector).value = "", selector);
}

async function dragAndDrop(page, start, end) {
  await page.mouse.move(start.x, start.y);
  await page.mouse.down();

  await page.mouse.move(end.x, end.y);
  await page.mouse.up();
}

async function waitForResponse(page, url) {
  return new Promise(resolve => {
    page.on("response", function callback(resp) {
      if (resp.url().includes(url)) {
        page.removeListener("response", callback)
        resolve(resp)
      }
    })
  })
}

async function isServiceReady(page, studyId, nodeId) {
  const endPoint = "/projects/" + studyId + "/nodes/" + nodeId;
  console.log("-- Is service ready", endPoint);
  const resp = await makeRequest(page, endPoint);
  if (resp === null) {
    return false;
  }

  const status = resp["service_state"];
  console.log("Status:", nodeId, status);
  const stopListening = [
    "running",
    "complete"
  ];
  return stopListening.includes(status);
}

async function getServiceUrl(page, studyId, nodeId) {
  const endPoint = "/projects/" + studyId + "/nodes/" + nodeId;
  console.log("-- get service url", endPoint);
  const resp = await makeRequest(page, endPoint);
  if (resp === null) {
    return null;
  }

  const service_basepath = resp["service_basepath"];
  const service_entrypoint = resp["entry_point"];
  const service_url = service_basepath + (service_entrypoint ? ("/" + service_entrypoint) : "/");
  console.log("Service URL:", nodeId, service_url);

  return service_url;
}

async function makePingRequest(page, path) {
  // https://github.com/Netflix/pollyjs/issues/149#issuecomment-481108446
  await page.setBypassCSP(true);
  return await page.evaluate(async (path) => {
    // eslint-disable-next-line no-useless-escape
    const url = (path).replace(/\/\//g, "\/");
    console.log("makePingRequest", url);
    return fetch(url, {
      accept: '*/*',
      cache: 'no-cache'
    })
      .then(response => {
        console.log("ping response status:", response.status);
        return response.ok;
      })
      .catch(error => console.error(error));
  }, path);
}

async function isServiceConnected(page, studyId, nodeId) {
  console.log("-- Is Service Connected", nodeId);
  const serviceUrl = await getServiceUrl(page, studyId, nodeId);
  const connected = await makePingRequest(page, serviceUrl);
  console.log(connected ? ("service " + nodeId + " connected") : ("service " + nodeId + " connecting..."), "--")
  return connected;
}

async function getStudyState(page, studyId) {
  const endPoint = "/projects/" + studyId + "/state";
  console.log("-- Get study state", endPoint);
  const resp = await makeRequest(page, endPoint);
  if (resp === null) {
    return null;
  }

  if (resp !== null && "state" in resp && "value" in resp["state"]) {
    const state = resp["state"]["value"];
    console.log("-----> study state", state);
    return state;
  }
  return null;
}

async function isStudyDone(page, studyId) {
  const state = await getStudyState(page, studyId);
  if (state) {
    const stopListening = [
      "SUCCESS",
      "FAILED"
    ];
    return stopListening.includes(state);
  }
  return false;
}

async function isStudyUnlocked(page, studyId) {
  const endPoint = "/projects/" + studyId + "/state";
  console.log("-- Is study closed", endPoint);
  const resp = await makeRequest(page, endPoint);
  if (resp === null) {
    return false;
  }

  if (resp !== null && "locked" in resp && "value" in resp["locked"]) {
    const studyLocked = resp["locked"]["value"];
    console.log("Study Lock Status:", studyId, studyLocked);
    return !studyLocked;
  }
  return false;
}

async function waitForValidOutputFile(page) {
  return new Promise((resolve, reject) => {
    page.on("response", function callback(resp) {
      const header = resp.headers();
      if (header['content-type'] === "binary/octet-stream") {
        resp.text().then(
          b => {
            if (b >= 0 && b <= 10) {
              page.removeListener("response", callback)
              resolve(b)
            }
            else {
              page.removeListener("response", callback)
              reject("Sleeper should have a number between 0 and 10 in the output")
            }
          },
          e => {
            page.removeListener("response", callback)
            reject("Failed downloading file")
          }
        );
      }
    })
  })
}

async function waitAndClick(page, id, timeout = null) {
  await page.waitForSelector(id, {
    timeout: (timeout ? timeout : 30000) // default 30s
  });
  await page.click(id);
}

async function clearInput(page, selector) {
  await page.waitForSelector(selector);
  await page.click(selector, {
    clickCount: 3
  });
  await page.type(selector, "");
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function createScreenshotsDir() {
  const fs = require('fs');
  const screenshotsDir = pathLib.join(__dirname, SCREENSHOTS_DIR);
  if (!fs.existsSync(screenshotsDir)) {
    fs.mkdirSync(screenshotsDir);
  }
  console.log("Screenshots directory:", screenshotsDir);
}

async function takeScreenshot(page, captureName = "") {
  const event = new Date();
  const time = event.toLocaleTimeString('de-CH') + `.${event.getMilliseconds()}`;
  let filename = time + "_" + captureName;
  filename = filename.split(":").join("-")
  filename = filename + ".jpg";
  const path = pathLib.join(__dirname, SCREENSHOTS_DIR, filename);
  try {
    await page.screenshot({
      fullPage: true,
      path: path,
      type: 'jpeg',
      quality: 15
    })
    console.log('screenshot taken', path);
  }
  catch (err) {
    console.error("Error taking screenshot", err);
  }
}

function extractWorkbenchData(data) {
  const workbenchData = {
    studyId: null,
    nodeIds: [],
    keyVersions: []
  };
  workbenchData.studyId = data["uuid"];
  if ("workbench" in data) {
    Object.keys(data["workbench"]).forEach(nodeId => {
      workbenchData.nodeIds.push(nodeId);
      const nodeKey = data["workbench"][nodeId]["key"];
      const nodeVersion = data["workbench"][nodeId]["version"];
      workbenchData.keyVersions.push(`${nodeKey}::${nodeVersion}`);
    })

  }
  return workbenchData;
}

function getGrayLogSnapshotUrl(targetUrl, since_secs = 30) {
  let snapshotUrl = null;

  // WARNING: This mappings might change
  const table = {
    "staging.osparc.io": "https://monitoring.staging.osparc.io/graylog/",
    "osparc.io": "https://monitoring.osparc.io/graylog/",
    "osparc-master.speag.com": "https://monitoring.osparc-master.speag.com/graylog/",
    "osparc-staging.speag.com": "https://monitoring.osparc.speag.com/graylog/",
    "osparc.speag.com": "https://monitoring.osparc.speag.com/graylog/",
  };

  const {
    hostname
  } = new URL(targetUrl)
  const monitoringBaseUrl = table[hostname] || null;

  if (monitoringBaseUrl) {
    const now_millisecs = Date.now();
    const from = encodeURIComponent(new Date(now_millisecs - since_secs * 1000).toISOString());
    const to = encodeURIComponent(new Date(now_millisecs).toISOString());

    const searchQuery = "image_name%3Aitisfoundation%2A"; // image_name:itisfoundation*
    snapshotUrl = `${monitoringBaseUrl}search?q=${searchQuery}&rangetype=absolute&from=${from}&to=${to}`;
  }

  return snapshotUrl
}

async function typeInInputElement(page, inputSelector, text) {
  const element = await page.waitForSelector(inputSelector);
  await element.focus();
  await page.keyboard.type(text, {
    delay: 100
  });
}

async function waitUntilVisible(page, selector, timeout = 10000) {
  const start = new Date().getTime();
  let isVisible = false;
  while (!isVisible && ((new Date().getTime() - start) < timeout)) {
    isVisible = isElementVisible(page, selector);
    await this.sleep(1000);
  }
}

function isElementVisible(page, selector) {
  return page.evaluate(selector => {
    const element = document.querySelector(selector)
    return !!(element && (element.offsetWidth || element.offsetHeight || element.getClientRects().length))
  }, selector);
}

async function clickLoggerTitle(page) {
  console.log("Click Logger");
  await this.waitAndClick(page, '[osparc-test-id="loggerTabButton"]')
}

async function getButtonsWithText(page, text) {
  const buttons = await page.$x(`//button[contains(text(), '${text}')]`);
  return buttons;
}


module.exports = {
  makeRequest,
  getUserAndPass,
  getDomain,
  getChildrenElements,
  getChildrenElementsBySelector,
  getNodeTreeItemIDs,
  getFileTreeItemIDs,
  getVisibleChildrenIDs,
  getDashboardCardLabel,
  getStyle,
  fetchReq,
  emptyField,
  dragAndDrop,
  waitForResponse,
  isServiceReady,
  isServiceConnected,
  getStudyState,
  isStudyDone,
  isStudyUnlocked,
  waitForValidOutputFile,
  waitAndClick,
  clearInput,
  sleep,
  createScreenshotsDir,
  takeScreenshot,
  extractWorkbenchData,
  parseCommandLineArguments,
  parseCommandLineArgumentsAnonymous,
  parseCommandLineArgumentsStudyDispatcherParams,
  getGrayLogSnapshotUrl,
  typeInInputElement,
  waitUntilVisible,
  isElementVisible,
  clickLoggerTitle,
  getButtonsWithText,
}
