const assert = require('assert');

const startPuppe = require('../utils/startPuppe');
const auto = require('../utils/auto');
const utils = require('../utils/utils');
const responses = require('../utils/responsesQueue');

class TutorialBase {
  constructor(url, templateName, user, pass, newUser, enableDemoMode = false) {
    this.__demo = enableDemoMode;
    this.__templateName = templateName;

    this.__url = url;
    this.__user = user;
    this.__pass = pass;
    this.__newUser = newUser;

    this.__browser = null;
    this.__page = null;
    this.__responsesQueue = null;

    this.__interval = null;

    this.__failed = false;
  }

  startScreenshooter() {
    try {
      utils.createScreenshotsDir();
    }
    catch (err) {
      console.error("Error creating screenshots directory", err);
      throw (err);
    }

    this.__interval = setInterval(async () => {
      await this.takeScreenshot();
    }, 2000);
  }

  stopScreenshooter() {
    clearInterval(this.__interval);
  }

  async beforeScript() {
    this.__browser = await startPuppe.getBrowser(this.__demo);
    this.__page = await startPuppe.getPage(this.__browser);
    this.__responsesQueue = new responses.ResponsesQueue(this.__page);
    return this.__page;
  }

  async __goTo() {
    console.log("Opening", this.__url);
    // Try to reach the website
    try {
      await this.__page.goto(this.__url);
    }
    catch (err) {
      console.error(this.__url, "can't be reached", err);
      throw (err);
    }
    const domain = utils.getDomain(this.__url);
    await this.takeScreenshot("landingPage_" + domain);
  }

  async start() {
    try {
      await this.beforeScript();
      await this.__goTo();

      const needsRegister = await this.registerIfNeeded();
      if (!needsRegister) {
        await this.login();
      }
    }
    catch (err) {
      console.error("Error starting", err);
      throw (err);
    }
  }

  async openStudyLink(openStudyTimeout = 20000) {
    this.__responsesQueue.addResponseListener("open");

    let resp = null;
    try {
      await this.__goTo();
      resp = await this.__responsesQueue.waitUntilResponse("open", openStudyTimeout);
    }
    catch (err) {
      console.error(this.__templateName, "could not be started", err);
      throw (err);
    }
    return resp;
  }

  async registerIfNeeded() {
    if (this.__newUser) {
      await auto.register(this.__page, this.__user, this.__pass);
      return true;
    }
    return false;
  }

  async login() {
    const resources = [{
      name: "Studies",
      request: "projects?type=user",
      listThem: false
    }, {
      name: "Templates",
      request: "projects?type=template",
      listThem: true
    }, {
      name: "Services",
      request: "catalog/services",
      listThem: false
    }];

    for (let i=0; i<resources.length; i++) {
      const resource = resources[i];
      this.__responsesQueue.addResponseListener(resource.request);
    }

    try {
      await auto.logIn(this.__page, this.__user, this.__pass);
    }
    catch (err) {
      console.error("Failed logging in", err);
      throw (err);
    }

    for (let i=0; i<resources.length; i++) {
      const resource = resources[i];
      try {
        const resp = await this.__responsesQueue.waitUntilResponse(resource.request);
        const respData = resp["data"];
        console.log(resource.request + " received:", respData.length);
        if (resource.listThem) {
          respData.forEach(item => {
            console.log(" - ", item.name);
          });
        }
      }
      catch (err) {
        console.error(resource.request + " could not be fetched", err);
        throw (err);
      }
    }
  }

  async waitForOpen() {
    this.__responsesQueue.addResponseListener("open");
    let resp = null;
    try {
      resp = await this.__responsesQueue.waitUntilResponse("open");
    }
    catch (err) {
      console.error(this.__templateName, "could not be started", err);
    }
    return resp;
  }

  async openTemplate(waitFor = 1000) {
    await this.takeScreenshot("dashboardOpenFirstTemplate_before");
    this.__responsesQueue.addResponseListener("projects?from_template=");
    this.__responsesQueue.addResponseListener("open");
    let resp = null;
    try {
      const templateFound = await auto.dashboardOpenFirstTemplate(this.__page, this.__templateName);
      assert(templateFound, "Expected template, got nothing. TIP: did you inject templates in database??")
      await this.__responsesQueue.waitUntilResponse("projects?from_template=");
      resp = await this.__responsesQueue.waitUntilResponse("open");
    }
    catch (err) {
      console.error(`"${this.__templateName}" template could not be started:\n`, err);
      throw (err);
    }
    await this.__page.waitFor(waitFor);
    await this.takeScreenshot("dashboardOpenFirstTemplate_after");
    return resp;
  }

  async openService(waitFor = 1000) {
    await this.takeScreenshot("dashboardOpenFirstService_before");
    this.__responsesQueue.addResponseListener("open");
    let resp = null;
    try {
      const serviceFound = await auto.dashboardOpenFirstService(this.__page, this.__templateName);
      assert(serviceFound, "Expected service, got nothing. TIP: is it available??");
      resp = await this.__responsesQueue.waitUntilResponse("open");
    }
    catch (err) {
      console.error(`"${this.__templateName}" service could not be started:\n`, err);
      throw (err);
    }
    await this.__page.waitFor(waitFor);
    await this.takeScreenshot("dashboardOpenFirstService_after");
    return resp;
  }

  async waitForServices(studyId, nodeIds, timeout = 40000) {
    if (nodeIds.length < 1) {
      return;
    }

    const start = new Date().getTime();
    while ((new Date().getTime()) - start < timeout) {
      for (let i = nodeIds.length - 1; i >= 0; i--) {
        const nodeId = nodeIds[i];
        if (await utils.isServiceReady(this.__page, studyId, nodeId)) {
          nodeIds.splice(i, 1);
        }
      }
      await utils.sleep(2500);
      if (nodeIds.length === 0) {
        console.log("Services ready in", ((new Date().getTime()) - start) / 1000);
        // after the service is responsive we need to wait a bit until the iframe is rendered
        await utils.sleep(3000);
        return;
      }
    }
    console.log("Timeout reached waiting for services", ((new Date().getTime()) - start) / 1000);
    return;
  }

  async waitForStudyRun(studyId, timeout = 60000) {
    const start = new Date().getTime();
    while ((new Date().getTime()) - start < timeout) {
      await utils.sleep(5000);
      if (await utils.isStudyDone(this.__page, studyId)) {
        return;
      }
    }
    console.log("Timeout reached waiting for study run", ((new Date().getTime()) - start) / 1000);
    return;
  }

  async waitForStudyUnlocked(studyId, timeout = 10000) {
    const start = new Date().getTime();
    while ((new Date().getTime()) - start < timeout) {
      await utils.sleep(timeout / 10);
      if (await utils.isStudyUnlocked(this.__page, studyId)) {
        return;
      }
    }
    console.log("Timeout reached waiting for study unlock", ((new Date().getTime()) - start) / 1000);
    return;
  }

  async restoreIFrame() {
    await auto.restoreIFrame(this.__page);
  }

  async clickLoggerTitle() {
    await auto.clickLoggerTitle(this.__page);
  }

  async runPipeline(studyId, timeout = 60000) {
    await this.clickLoggerTitle();

    await this.takeScreenshot("runStudy_before");
    await auto.runStudy(this.__page);
    await this.waitForStudyRun(studyId, timeout);
    await this.takeScreenshot("runStudy_after");
  }

  async openNode(nodePosInTree = 0) {
    await auto.openNode(this.__page, nodePosInTree);
    await this.takeScreenshot('openNode_' + nodePosInTree);
  }

  async getIframe() {
    return await this.__page.$$("iframe");
  }

  async openNodeFiles(nodePosInTree = 0) {
    const nodeId = await auto.openNode(this.__page, nodePosInTree);
    this.__responsesQueue.addResponseListener("storage/locations/0/files/metadata?uuid_filter=" + nodeId);
    await auto.openNodeFiles(this.__page);
    try {
      await this.__responsesQueue.waitUntilResponse("storage/locations/0/files/metadata?uuid_filter=" + nodeId);
    }
    catch (err) {
      console.error(err);
      throw (err);
    }
  }

  async retrieve(waitAfterRetrieve = 5000) {
    await auto.clickRetrieve(this.__page);
    await this.__page.waitFor(waitAfterRetrieve);
  }

  async openNodeRetrieveAndRestart(nodePosInTree = 0) {
    await this.takeScreenshot("openNodeRetrieveAndRestart_before");
    await auto.openNode(this.__page, nodePosInTree);
    await this.retrieve();
    await auto.clickRestart(this.__page);
    await this.takeScreenshot("openNodeRetrieveAndRestart_after");
  }

  async checkResults(expecedNFiles = 1) {
    await this.takeScreenshot("checkResults_before");
    try {
      await auto.checkDataProducedByNode(this.__page, expecedNFiles);
    }
    catch (err) {
      console.error("Failed checking Data Produced By Node", err);
      throw (err);
    }
    await this.takeScreenshot("checkResults_after");
  }

  async toDashboard() {
    await this.takeScreenshot("toDashboard_before");
    this.__responsesQueue.addResponseListener("projects");
    this.__responsesQueue.addResponseListener(":close");
    try {
      await auto.toDashboard(this.__page);
      await this.__responsesQueue.waitUntilResponse("projects");
      await this.__responsesQueue.waitUntilResponse(":close");
    }
    catch (err) {
      console.error("Failed going to dashboard study", err);
      throw (err);
    }
    await this.takeScreenshot("toDashboard_after");
  }

  async closeStudy() {
    await this.takeScreenshot("closeStudy_before");
    this.__responsesQueue.addResponseListener(":close");
    try {
      await auto.toDashboard(this.__page);
      await this.__responsesQueue.waitUntilResponse(":close");
    }
    catch (err) {
      console.error("Failed closing study", err);
      throw (err);
    }
    await this.takeScreenshot("closeStudy_after");
  }

  async removeStudy(studyId) {
    await this.takeScreenshot("deleteFirstStudy_before");
    try {
      // await this.waitForStudyUnlocked(studyId);
      const nTries = 3;
      for (let i = 0; i < nTries; i++) {
        const cardUnlocked = await auto.deleteFirstStudy(this.__page, this.__templateName);
        if (cardUnlocked) {
          break;
        }
        console.log(studyId, "study card still locked");
        await utils.sleep(3000);
      }
    }
    catch (err) {
      console.error("Failed deleting study", err);
      throw (err);
    }
    await this.takeScreenshot("deleteFirstStudy_after");
  }

  async logOut() {
    await auto.logOut(this.__page);
  }

  async close() {
    await utils.sleep(2000);
    await this.__browser.close();
  }

  async waitFor(waitFor) {
    await this.__page.waitFor(waitFor);
  }

  async takeScreenshot(screenshotTitle) {
    // Generates an URL that points to the backend logs at this time
    const snapshotUrl = utils.getGrayLogSnapshotUrl(this.__url, 30);
    if (snapshotUrl) {
      console.log("Backend Snapshot: ", snapshotUrl)
    }

    if (this.__demo) {
      return;
    }

    let title = this.__templateName;
    if (screenshotTitle) {
      title += '_' + screenshotTitle;
    }
    await utils.takeScreenshot(this.__page, title);
  }

  getTutorialFailed() {
    return this.__failed;
  }

  setTutorialFailed(failed) {
    this.__failed = failed;
  }
}

module.exports = {
  TutorialBase
}
