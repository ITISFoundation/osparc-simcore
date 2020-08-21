

function parseCommandLineArguments(args) {
  //
  // node $tutorial.js [url] [user] [password] [--demo]
  //
  //

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
  await page.evaluate(selector => {
    document.querySelector(selector).value = "";
  }, selector);
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function __addZerosAtTheBeggining(input) {
  return String(input).padStart(2, "0");
}

async function takeScreenshot(page, captureName) {
  const d = new Date();
  const date = __addZerosAtTheBeggining(d.getMonth()+1) +"-"+ __addZerosAtTheBeggining(d.getDate());
  const time = __addZerosAtTheBeggining(d.getHours()) +":"+ __addZerosAtTheBeggining(d.getMinutes()) +":"+ __addZerosAtTheBeggining(d.getSeconds());
  const timeStamp = date +"_"+ time;
  captureName = captureName.replace("undefined", "");
  await page.screenshot({
    fullPage: true,
    path: 'screenshots/'+timeStamp+'_'+captureName+'.jpg',
    type: 'jpeg',
  })
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
  waitForValidOutputFile,
  waitAndClick,
  clearInput,
  sleep,
  takeScreenshot,
  extractWorkbenchData,
  parseCommandLineArguments
}
