async function getPageTitle(page) {
  return await page.title();
}

function getPageUrl(page) {
  return page.url();
}

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

const request = require('request');
function readFileFromLink(downloadUrl) {
  request.get(downloadUrl, (error, response, body) => {
    if (!error && response.statusCode == 200) {
      console.log('body', body);
    }
  });
}

function __logMe(msg, level='log') {
  if (level==='error') {
    console.error(`Error ${msg}`);
  }
  else {
    console.log("Console", msg.text());
  }
}

function addPageListeners(page) {
  // Emitted when a script within the page uses `console`
  page.on('console', __logMe);
  // Emitted when the page emits an error event (for example, the page crashes)
  page.on('error', __logMe);
  // Emitted when a script within the page has uncaught exception
  page.on('pageerror', __logMe);
}

function removePageListeners(page) {
  // Emitted when a script within the page uses `console`
  page.removeListener('console', __logMe);
  // Emitted when the page emits an error event (for example, the page crashes)
  page.removeListener('error', __logMe);
  // Emitted when a script within the page has uncaught exception
  page.removeListener('pageerror', __logMe);
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
        resolve(resp)
        page.removeListener("response", callback)
      }
    })
  })
}

module.exports = {
  getPageTitle,
  getPageUrl,
  getRandUserAndPass,
  getNodeTreeItemIDs,
  getFileTreeItemIDs,
  getVisibleChildrenIDs,
  fetch,
  emptyField,
  readFileFromLink,
  addPageListeners,
  removePageListeners,
  waitForResponse,
  dragAndDrop,
}
