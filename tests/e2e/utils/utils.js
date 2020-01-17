function getRandUserAndPass() {
  const randUser = Math.random().toString(36).substring(7);
  const user = 'puppeteer_'+randUser+'@itis.testing';
  const pass = Math.random().toString(36).substring(7);
  return {
    user,
    pass
  }
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
  const responseEnv = await page.evaluate(async (url, apiVersion, endpoint) => {
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

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function takeScreenshot(page, captureName) {
  await page.screenshot({
    fullPage: true,
    path: 'screenshots/'+captureName+'.jpg',
    type: 'jpeg',
  })
}

module.exports = {
  getRandUserAndPass,
  getNodeTreeItemIDs,
  getFileTreeItemIDs,
  getVisibleChildrenIDs,
  fetch,
  emptyField,
  dragAndDrop,
  waitForResponse,
  waitForValidOutputFile,
  sleep,
  takeScreenshot,
}
