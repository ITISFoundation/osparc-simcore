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

    this.__services = null;

    this.__interval = null;

    this.__failed = false;

    this.startScreenshooter()
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
    }, 4000);
  }

  stopScreenshooter() {
    clearInterval(this.__interval);
  }

  async beforeScript() {
    this.__browser = await startPuppe.getBrowser(this.__demo);
    this.__page = await startPuppe.getPage(this.__browser);
    this.__page.setExtraHTTPHeaders({
      "X-Simcore-User-Agent": "puppeteer"
    });
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

    await auto.acceptCookies(this.__page);
    await this.takeScreenshot("postCookies_" + domain);

    // eslint-disable-next-line no-undef
    const commit = await this.__page.evaluate(() => qx.core.Environment.get("osparc.vcsRef"));
    console.log("commit", commit);
  }

  async __printMe() {
    const resp = await utils.makeRequest(this.__page, "/me");
    if (resp) {
      console.log("login:", resp["login"]);
      console.log("user_id:", resp["id"]);
    }
    else {
      console.log("Not found");
    }
  }

  async start() {
    try {
      await this.beforeScript();
      await this.__goTo();

      // Logs notifications
      const waitForFlash = () => {
        this.__page.waitForSelector('[qxclass="osparc.ui.message.FlashMessage"]', {
          timeout: 0
        }).then(async () => {
          const messages = await this.__page.$$eval('[qxclass="osparc.ui.message.FlashMessage"]',
            elements => {
              const flashText = elements.map(element => element.textContent)
              elements.forEach(element => element.remove())
              return flashText
            })
          console.log('Flash message', messages)
          setTimeout(waitForFlash, 0)
        }).catch(() => { })
      }
      setTimeout(waitForFlash, 0)

      const needsRegister = await this.registerIfNeeded();
      if (!needsRegister) {
        await this.login();
      }
      await this.__printMe();
    }
    catch (err) {
      console.error("Error starting", err);
      throw (err);
    }
  }

  async closeQuickStart() {
    await this.takeScreenshot("preCloseQuickStart");
    await auto.closeQuickStart(this.__page);
    await this.takeScreenshot("postCloseQuickStart");
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

    for (let i = 0; i < resources.length; i++) {
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

    for (let i = 0; i < resources.length; i++) {
      const resource = resources[i];
      try {
        const resp = await this.__responsesQueue.waitUntilResponse(resource.request);
        const respData = resp["data"];
        console.log(resource.name + " received:", respData.length);
        if (resource.name === "Services") {
          this.__services = respData;
        }
        if (resource.listThem) {
          respData.forEach(item => {
            console.log(" - ", item.name);
          });
        }
      }
      catch (err) {
        console.error(resource.name + " could not be fetched", err);
        throw (err);
      }
    }
  }

  getReceivedServices() {
    return this.__services;
  }

  async checkFirstStudyId(studyId) {
    await this.__page.waitForSelector('[osparc-test-id="studiesList"]');
    await this.waitFor(5000, "Wait for studies to be loaded");
    const studies = await utils.getVisibleChildrenIDs(this.__page, '[osparc-test-id="studiesList"]');
    console.log("checkFirstStudyId", studyId);
    console.log(studies);
    if (studyId !== studies[0]) {
      throw (studyId + " not found");
    }
  }

  async waitForOpen() {
    this.__responsesQueue.addResponseListener(":open");
    let resp = null;
    try {
      resp = await this.__responsesQueue.waitUntilResponse(":open");
    }
    catch (err) {
      console.error(this.__templateName, "could not be started", err);
    }
    return resp;
  }

  async startNewPlan() {
    await this.takeScreenshot("startNewPlan_before");
    this.__responsesQueue.addResponseListener("projects?from_study=");
    this.__responsesQueue.addResponseListener(":open");
    let resp = null;
    try {
      await this.waitFor(2000);
      await auto.dashboardNewPlan(this.__page);
      await this.__responsesQueue.waitUntilResponse("projects?from_study=");
      resp = await this.__responsesQueue.waitUntilResponse(":open");
      const studyId = resp["data"]["uuid"];
      console.log("Study ID:", studyId);
    }
    catch (err) {
      console.error(`New Plan could not be started:\n`, err);
      throw (err);
    }
    await this.waitFor(2000);
    await this.takeScreenshot("startNewPlan_after");
    return resp;
  }

  async startSim4LifeLite() {
    await this.takeScreenshot("startSim4LifeLite_before");
    this.__responsesQueue.addResponseListener(":open");
    let resp = null;
    try {
      await this.waitFor(2000);
      await auto.dashboardStartSim4LifeLite(this.__page);
      resp = await this.__responsesQueue.waitUntilResponse(":open");
      const studyId = resp["data"]["uuid"];
      console.log("Study ID:", studyId);
    }
    catch (err) {
      console.error(`Sim4Life Lite could not be started:\n`, err);
      throw (err);
    }
    await this.waitFor(2000);
    await this.takeScreenshot("startSim4LifeLite_after");
    return resp;
  }

  async openStudyLink(openStudyTimeout = 20000) {
    this.__responsesQueue.addResponseListener(":open");

    let resp = null;
    try {
      await this.__goTo();
      resp = await this.__responsesQueue.waitUntilResponse(":open", openStudyTimeout);
      await this.__printMe();
      const studyId = resp["data"]["uuid"];
      console.log("Study ID:", studyId);
    }
    catch (err) {
      console.error(this.__templateName, "could not be started", err);
      throw (err);
    }
    return resp;
  }

  async openTemplate(waitFor = 1000) {
    await this.takeScreenshot("dashboardOpenFirstTemplate_before");
    this.__responsesQueue.addResponseListener("projects?from_study=");
    this.__responsesQueue.addResponseListener(":open");
    let resp = null;
    try {
      const templateFound = await auto.dashboardOpenFirstTemplate(this.__page, this.__templateName);
      assert(templateFound, "Expected template, got nothing. TIP: did you inject templates in database??")
      await this.__responsesQueue.waitUntilResponse("projects?from_study=");
      resp = await this.__responsesQueue.waitUntilResponse(":open");
      const studyId = resp["data"]["uuid"];
      console.log("Study ID:", studyId);
    }
    catch (err) {
      console.error(`"${this.__templateName}" template could not be started:\n`, err);
      throw (err);
    }
    await this.waitFor(waitFor);
    await this.takeScreenshot("dashboardOpenFirstTemplate_after");
    return resp;
  }

  async openService(waitFor = 1000) {
    await this.takeScreenshot("dashboardOpenService_before");
    this.__responsesQueue.addResponseListener(":open");
    let resp = null;
    try {
      const serviceFound = await auto.dashboardOpenService(this.__page, this.__templateName);
      assert(serviceFound, "Expected service, got nothing. TIP: is it available??");
      resp = await this.__responsesQueue.waitUntilResponse(":open");
      const studyId = resp["data"]["uuid"];
      console.log("Study ID:", studyId);
    }
    catch (err) {
      console.error(`"${this.__templateName}" service could not be started:\n`, err);
      throw (err);
    }
    await this.waitFor(waitFor);
    await this.takeScreenshot("dashboardOpenService_after");
    return resp;
  }

  async getAppModeSteps() {
    await this.__page.waitForSelector('[osparc-test-id="appModeButtons"]')
    const appModeButtonsAllIds = await utils.getVisibleChildrenIDs(this.__page, '[osparc-test-id="appModeButtons"]');
    if (appModeButtonsAllIds.length < 1) {
      throw ("appModeButtons not found");
    }
    console.log("appModeButtonsAllIds", appModeButtonsAllIds);
    const appModeButtonIds = appModeButtonsAllIds.filter(btn => btn && btn.includes("AppMode_StepBtn"));
    if (appModeButtonIds.length < 1) {
      throw ("appModeButtons filtered not found");
    }
    return appModeButtonIds;
  }

  async waitForServices(studyId, nodeIds, timeout = 40000, waitForConnected = true) {
    console.log("waitForServices timeout:", timeout);
    if (nodeIds.length < 1) {
      return;
    }

    const start = new Date().getTime();
    while ((new Date().getTime()) - start < timeout) {
      for (let i = nodeIds.length - 1; i >= 0; i--) {
        const nodeId = nodeIds[i];
        let isLoaded = await utils.isServiceReady(this.__page, studyId, nodeId);
        if (waitForConnected) {
          isLoaded = isLoaded && await utils.isServiceConnected(this.__page, studyId, nodeId);
        }

        if (isLoaded) {
          nodeIds.splice(i, 1);
        }
      }

      if (nodeIds.length === 0) {
        console.log("Services ready in", ((new Date().getTime()) - start) / 1000);
        // after the service is responsive we need to wait a bit until the iframe is rendered
        await this.waitFor(3000);
        return;
      }

      await this.waitFor(2500);
    }
    const errorMsg = "Timeout reached waiting for services";
    console.log(errorMsg, ((new Date().getTime()) - start) / 1000);
    throw new Error(errorMsg);
  }

  async waitForStudyDone(studyId, timeout = 60000) {
    const start = new Date().getTime();
    while ((new Date().getTime()) - start < timeout) {
      await this.waitFor(5000);
      if (await utils.isStudyDone(this.__page, studyId)) {
        await utils.takeScreenshot(this.__page, 'run_pipeline_done');
        if (await utils.getStudyState(this.__page, studyId) === "FAILED") {
          throw new Error("Pipeline failed");
        }
        return;
      }
    }
    console.log("Timeout reached waiting for study done ", ((new Date().getTime()) - start) / 1000);
    await utils.takeScreenshot(this.__page, 'run_pipeline_timeout_reached');
    throw new Error("Pipeline timed out");
  }

  async restoreIFrame() {
    await auto.restoreIFrame(this.__page);
  }

  async findLogMessage(text) {
    return await auto.findLogMessage(this.__page, text);
  }

  async showLogger(show) {
    await auto.showLogger(this.__page, show);
  }

  async takeLoggerScreenshot() {
    await this.takeScreenshot("logger_before");
    await this.showLogger(true);
    await this.takeScreenshot("logger_after");
  }

  async runPipeline() {
    await this.takeScreenshot("runStudy_before");
    await auto.runStudy(this.__page);
    await this.takeScreenshot("runStudy_after");
  }

  async openNode(nodePosInTree = 0) {
    await auto.openNode(this.__page, nodePosInTree);
    // Iframes get loaded on demand, wait 5"
    await this.waitFor(5000);
    await this.takeScreenshot('openNode_' + nodePosInTree);
  }

  async __getIframeHandles() {
    return await this.__page.$$("iframe");
  }

  async __getIframes() {
    const iframeHandles = await this.__getIframeHandles();
    const iframes = [];
    for (let i = 0; i < iframeHandles.length; i++) {
      const frame = await iframeHandles[i].contentFrame();
      iframes.push(frame);
    }
    return iframes;
  }

  async getIframe(nodeId) {
    const iframes = await this.__getIframes();
    const nodeIframe = iframes.find(iframe => iframe._url.includes(nodeId));
    return nodeIframe;
  }

  async openNodeFiles(nodeId) {
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

  async openNodeFilesAppMode(nodeId) {
    this.__responsesQueue.addResponseListener("storage/locations/0/files/metadata?uuid_filter=" + nodeId);
    await auto.openNodeFilesAppMode(this.__page);
    try {
      await this.__responsesQueue.waitUntilResponse("storage/locations/0/files/metadata?uuid_filter=" + nodeId);
    }
    catch (err) {
      console.error(err);
      throw (err);
    }
  }

  async waitAndClick(osparcTestId) {
    await utils.waitAndClick(this.__page, `[osparc-test-id=${osparcTestId}]`);
  }

  async closeNodeFiles() {
    await this.waitAndClick("nodeDataManagerCloseBtn");
  }

  async __checkNItemsInFolder(fileNames, openOutputsFolder = false) {
    await this.takeScreenshot("checkNodeOutputs_before");
    console.log("N items in folder. Expected:", fileNames);
    if (openOutputsFolder) {
      const itemTexts = await this.__page.$$eval('[osparc-test-id="FolderViewerItem"]',
        elements => elements.map(el => el.textContent)
      );
      console.log("Service data items", itemTexts);
      const items = await this.__page.$$('[osparc-test-id="FolderViewerItem"]');
      let outputsFound = false;
      for (let i=0; i<items.length; i++) {
        const text = await items[i].evaluate(el => el.textContent);
        if (text.includes("output")) {
          console.log("Opening outputs folder");
          // that's the way to double click........
          await items[i].click();
          await items[i].click({
            clickCount: 2
          });
          outputsFound = true;
        }
      }
      if (outputsFound) {
        await this.takeScreenshot("outputs_folder");
      }
      else {
        throw("outputs folder not found");
      }
    }
    const files = await this.__page.$$eval('[osparc-test-id="FolderViewerItem"]',
      elements => elements.map(el => el.textContent)
    );
    console.log("N items in folder. Received:", files);
    if (files.length === fileNames.length) {
      console.log("Number of files is correct")
      await this.takeScreenshot("checkNodeOutputs_after");
      await this.closeNodeFiles();
    }
    else {
      await this.takeScreenshot("checkNodeOutputs_after");
      await this.closeNodeFiles();
      throw("Number of files is incorrect");
    }
  }

  async checkNodeOutputs(nodePos, fileNames, openOutputsFolder = false) {
    try {
      const nodeId = await auto.openNode(this.__page, nodePos);
      await this.openNodeFiles(nodeId);
      await this.__checkNItemsInFolder(fileNames, openOutputsFolder);
    }
    catch (err) {
      console.error("Results don't match", err);
      throw (err)
    }
  }

  async checkNodeOutputsAppMode(nodeId, fileNames, openOutputsFolder = false) {
    try {
      await this.openNodeFilesAppMode(nodeId);
      await this.__checkNItemsInFolder(fileNames, openOutputsFolder);
    }
    catch (err) {
      console.error("Results don't match", err);
      throw (err)
    }
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

  async removeStudy(studyId, waitFor = 5000) {
    await this.waitFor(waitFor, 'Wait to be unlocked');
    await this.takeScreenshot("deleteFirstStudy_before");
    const intervalWait = 3000;
    try {
      const nTries = 20;
      let i
      for (i = 0; i < nTries; i++) {
        const cardUnlocked = await auto.deleteFirstStudy(this.__page, this.__templateName);
        if (cardUnlocked) {
          console.log("Study Card unlocked in " + (waitFor + intervalWait*i) + "s");
          break;
        }
        console.log(studyId, "study card still locked");
        await this.waitFor(intervalWait, 'Waiting in case the study was locked');
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
    this.stopScreenshooter()
    await this.waitFor(2000);
    await this.__browser.close();
  }

  async waitFor(waitFor, reason) {
    if (reason) {
      console.log(`Waiting for ${waitFor}ms. Reason: ${reason}`);
    }
    else {
      console.log(`Waiting for ${waitFor}ms.`);
    }
    await utils.sleep(waitFor);
    await this.takeScreenshot('waitFor_finished')
  }

  async testS4L(s4lNodeId) {
    await this.waitFor(20000, 'Wait for the spash screen to disappear');

    // do some basic interaction
    const s4lIframe = await this.getIframe(s4lNodeId);
    const modelTree = await s4lIframe.$('.model-tree');
    const modelItems = await modelTree.$$('.MuiTreeItem-label');
    const nLabels = modelItems.length;
    if (nLabels > 1) {
      modelItems[0].click();
      await this.waitFor(2000, 'Model clicked');
      await this.takeScreenshot('ModelClicked');
      modelItems[1].click();
      await this.waitFor(2000, 'Grid clicked');
      await this.takeScreenshot('GridlClicked');
    }
  }

  async takeScreenshot(screenshotTitle) {
    // Generates an URL that points to the backend logs at this time
    const snapshotUrl = utils.getGrayLogSnapshotUrl(this.__url, 30);
    if (snapshotUrl) {
      console.log("Backend Snapshot: ", snapshotUrl)
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

  async setTutorialFailed(failed) {
    if (failed) {
      await this.takeLoggerScreenshot();
    }
    this.__failed = failed;
  }
}

module.exports = {
  TutorialBase
}
