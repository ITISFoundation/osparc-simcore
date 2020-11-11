const pathLib = require('path');

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

function  __getRandUserAndPass() {
  const randUser = Math.random().toString(36).substring(7);
  const user = 'puppeteer_'+randUser+'@itis.testing';
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
      for (let i=1; i<tree.children.length; i++) {
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
      for (let i=1; i<tree.children.length; i++) {
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

async function fetch(endpoint) {
  const responseEnv = await page.evaluate(
    // NOTE: without the following comment it fails here with some weird message
    /* istanbul ignore next */
    async (url, apiVersion, endpoint) => {
      const response = await fetch(url+apiVersion+endpoint);
      return await response.json();
    }, url, apiVersion, endpoint);
  return responseEnv;
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

async function __makeRequest(url) {
  const resp = await page.evaluate(async (url) => {
    const resp = await fetch(url);
    const jsonResp = await resp.json();
    console.log(jsonResp)
    return jsonResp;
  }, url);
  return resp;
}

async function isServiceReady(page, prefix, studyId, nodeId) {
  const url = prefix + "/projects/" + studyId +"/nodes/" + nodeId;
  console.log("-- Is service ready", url, ":");
  const resp = __makeRequest(page, url);

  const status = resp["data"]["service_state"];
  console.log("Status:", nodeId, status);
  const stopListening = [
    "running",
    "complete",
    "failed"
  ];
  return stopListening.includes(status);
}

async function isStudyDone(page, prefix, studyId) {
  const url = prefix + "/projects/" + studyId +"/state";
  console.log("-- Is study done", url, ":");
  const resp = __makeRequest(page, url);

  const pipelineStatus = resp["data"]["state"];
  console.log("Pipeline Status:", studyId, pipelineStatus);
  const stopListening = [
    "SUCCESS",
    "FAILED"
  ];
  return stopListening.includes(status);
}

async function waitForValidOutputFile(page) {
  return new Promise((resolve, reject) => {
    page.on("response", function callback(resp) {
      const header = resp.headers();
      if (header['content-type'] === "binary/octet-stream") {
        resp.text().then(
          b => {
            if (b>=0 && b<=10) {
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

async function waitAndClick(page, id) {
  await page.waitForSelector(id, {
    timeout: 30000 // default 30s
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
  catch(err) {
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

module.exports = {
  getUserAndPass,
  getDomain,
  getNodeTreeItemIDs,
  getFileTreeItemIDs,
  getVisibleChildrenIDs,
  fetch,
  emptyField,
  dragAndDrop,
  waitForResponse,
  isServiceReady,
  isStudyDone,
  waitForValidOutputFile,
  waitAndClick,
  clearInput,
  sleep,
  createScreenshotsDir,
  takeScreenshot,
  extractWorkbenchData,
  parseCommandLineArguments
}
