const pathLib = require('path');
const URL = require('url').URL;

const SCREENSHOTS_DIR = "../screenshots/";

function parseCommandLineArguments(args) {
  // node $tutorial.js [url] [user] [password] [--demo]

  if (args.length < 1) {
    console.log('More arguments expected:  $tutorial.js [url] [user] [password] [--demo]');
    process.exit(1);
  }

  const url = args[0];
  const enableDemoMode = args.includes("--demo");
  const {
    user,
    pass,
    newUser
  } = getUserAndPass(args);

  return {
    url,
    user,
    pass,
    newUser,
    enableDemoMode
  }
}

function parseCommandLineArgumentsTemplate(args) {
  // node $template.js [url] [template_uuid] [--demo]

  if (args.length < 2) {
    console.log('More arguments expected: $template.js [url_prefix] [template_uuid] [--demo]');
    process.exit(1);
  }

  const urlPrefix = args[0];
  const templateUuid = args[1];
  const enableDemoMode = args.includes("--demo");

  return {
    urlPrefix,
    templateUuid,
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

function __getRandUserAndPass() {
  const randUser = Math.random().toString(36).substring(7);
  const user = 'puppeteer_' + randUser + '@itis.testing';
  const pass = Math.random().toString(36).substring(7);
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

async function getNodeTreeItemIDs(page) {
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
  }, '[osparc-test-id="nodeTreeItem_root"]');
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
    const jsonResp = await resp.json();
    return jsonResp["data"];
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

  const status = resp["service_state"];
  console.log("Status:", nodeId, status);
  const stopListening = [
    "running",
    "complete",
    "failed"
  ];
  return stopListening.includes(status);
}

async function getServiceUrl(page, studyId, nodeId) {
  const endPoint = "/projects/" + studyId + "/nodes/" + nodeId;
  console.log("-- get service url", endPoint);
  const resp = await makeRequest(page, endPoint);

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
  console.log(connected ? ("service " + nodeId + " connected") : ("service" + nodeId + " connecting..."), "--")
  return connected;
}

async function isStudyDone(page, studyId) {
  const endPoint = "/projects/" + studyId + "/state";
  console.log("-- Is study done", endPoint);
  const resp = await makeRequest(page, endPoint);

  const pipelineStatus = resp["state"]["value"];
  console.log("Pipeline Status:", studyId, pipelineStatus);
  const stopListening = [
    "SUCCESS",
    "FAILED"
  ];
  return stopListening.includes(pipelineStatus);
}

async function isStudyUnlocked(page, studyId) {
  const endPoint = "/projects/" + studyId + "/state";
  console.log("-- Is study closed", endPoint);
  const resp = await makeRequest(page, endPoint);

  const studyLocked = resp["locked"]["value"];
  console.log("Study Lock Status:", studyId, studyLocked);
  return !studyLocked;
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
  await page.type('[osparc-test-id="sideSearchFiltersTextFld"]', "");
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
  const time = event.toLocaleTimeString('de-CH');
  let filename = time + "_" + captureName;
  filename = filename.split(":").join("-")
  filename = filename + ".jpg";
  const path = pathLib.join(__dirname, SCREENSHOTS_DIR, filename);
  console.log(path);

  try {
    await page.screenshot({
      fullPage: true,
      path: path,
      type: 'jpeg',
      quality: 15
    })
  }
  catch (err) {
    console.error("Error taking screenshot", err);
  }
}

function extractWorkbenchData(data) {
  const workbenchData = {
    studyId: null,
    nodeIds: []
  };
  workbenchData.studyId = data["uuid"];
  if ("workbench" in data) {
    workbenchData.nodeIds = Object.keys(data["workbench"]);
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

function isElementVisible(page, selector) {
  return page.evaluate(selector => {
    const element = document.querySelector(selector)
    return !!(element && (element.offsetWidth || element.offsetHeight || element.getClientRects().length))
  }, selector);
}

async function clickLoggerTitle(page) {
  console.log("Click LoggerTitle");
  await this.waitAndClick(page, '[osparc-test-id="studyLoggerTitleLabel"]')
}


module.exports = {
  getUserAndPass,
  getDomain,
  getNodeTreeItemIDs,
  getFileTreeItemIDs,
  getVisibleChildrenIDs,
  getStyle,
  fetchReq,
  makeRequest,
  emptyField,
  dragAndDrop,
  waitForResponse,
  isServiceReady,
  isServiceConnected,
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
  parseCommandLineArgumentsTemplate,
  getGrayLogSnapshotUrl,
  typeInInputElement,
  isElementVisible,
  clickLoggerTitle,
}
