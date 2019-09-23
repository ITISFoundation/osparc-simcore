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


// https://medium.com/@viviancpy/save-screenshot-of-websites-with-puppeteer-cloudinary-and-heroku-1-3-bba6082d21d0
require('dotenv').config();
const cloudinary = require('cloudinary');
cloudinary.config({
  cloud_name: process.env.CLOUD_NAME,
  api_key: process.env.CLOUD_API_KEY,
  api_secret: process.env.CLOUD_API_SECRET,
});

function cloudinaryPromise(shotResult, cloudinary_options){
  return new Promise(function(res, rej){
    cloudinary.v2.uploader.upload_stream(cloudinary_options,
      function (error, cloudinary_result) {
        if (error){
          console.error('Upload to cloudinary failed: ', error);
          rej(error);
        }
        res(cloudinary_result);
      }
    ).end(shotResult);
  });
}

async function doScreenCapture(page, captureName) {
  // details are skipped here. Refer to in previous step
  const shotResult = await page.screenshot({
    fullPage: true
  }).then((result) => {
    console.log(`${captureName} succeed.`);
    return result;
  }).catch(e => {
    console.error(`${captureName} failed`, e);
    return false;
  });

  const d = new Date();
  const current_time = `${d.getFullYear()}_${d.getMonth()+1}_${d.getDate()}_${d.getHours()}_${d.getMinutes()}`;
  const cloudinary_options = {
    public_id: `newCapture/${current_time}_${captureName}`
  };
  if (shotResult) {
    return cloudinaryPromise(shotResult, cloudinary_options);
  }
  else {
    return null;
  }
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
  addPageListeners,
  removePageListeners,
  dragAndDrop,
  doScreenCapture,
}
