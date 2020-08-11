const fs = require('fs');
const assert = require('assert');

const startPuppe = require('../utils/startPuppe');
const auto = require('../utils/auto');
const utils = require('../utils/utils');
const responses = require('../utils/responsesQueue');

class TutorialBase {
  constructor(url, user, pass, newUser, templateName, enableDemoMode=false) {
    this.__demo = enableDemoMode;
    this.__templateName = templateName;

    this.__url = url;
    this.__user = user;
    this.__pass = pass;
    this.__newUser = newUser;

    this.__browser = null;
    this.__page = null;
    this.__responsesQueue = null;
  }

  init() {
    const dir = 'screenshots';
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir);
    }
  }

  async beforeScript() {
    this.__browser = await startPuppe.getBrowser(this.__demo);
    this.__page = await startPuppe.getPage(this.__browser);
    this.__responsesQueue = new responses.ResponsesQueue(this.__page);
    return this.__page;
  }

  async goTo() {
    console.log("Opening", this.__url);
    // Try to reach the website
    try {
      await this.__page.goto(this.__url);
    }
    catch(err) {
      console.error(this.__url, "can't be reached", err);
    }
    const domain = utils.getDomain(this.__url);
    await utils.takeScreenshot(this.__page, this.__templateName + "_landingPage_" + domain);
  }

  async openStudyLink(openStudyTimeout = 20000) {
    this.__responsesQueue.addResponseListener("open");

    await this.goTo();

    let resp = null;
    try {
      resp = await this.__responsesQueue.waitUntilResponse("open", openStudyTimeout);
    }
    catch(err) {
      console.error(this.__templateName, "could not be started", err);
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
    this.__responsesQueue.addResponseListener("projects?type=template");
    this.__responsesQueue.addResponseListener("catalog/dags");
    this.__responsesQueue.addResponseListener("services");
    await auto.logIn(this.__page, this.__user, this.__pass);
    try {
      const resp = await this.__responsesQueue.waitUntilResponse("projects?type=template");
      const templates = resp["data"];
      console.log("Templates received", templates.length);
      templates.forEach(template => {
        console.log(" - ", template.name);
      });
    }
    catch(err) {
      console.error("Templates could not be fetched", err);
    }
    try {
      const resp = await this.__responsesQueue.waitUntilResponse("catalog/dags");
      const dags = resp["data"];
      console.log("DAGs received:", dags.length);
      dags.forEach(dag => {
        console.log(" - ", dag.name);
      });
    }
    catch(err) {
      console.error("DAGs could not be fetched", err);
    }
    try {
      const resp = await this.__responsesQueue.waitUntilResponse("services");
      const services = resp["data"];
      console.log("Services received:", services.length);
    }
    catch(err) {
      console.error("Services could not be fetched", err);
    }
  }

  async waitForOpen() {
    this.__responsesQueue.addResponseListener("open");
    let resp = null;
    try {
      resp = await this.__responsesQueue.waitUntilResponse("open");
    }
    catch(err) {
      console.error(this.__templateName, "could not be started", err);
    }
    return resp;
  }

  async openTemplate(waitFor = 1000) {
    await utils.takeScreenshot(this.__page, this.__templateName + "_dashboardOpenFirstTemplate_before");
    this.__responsesQueue.addResponseListener("projects?from_template=");
    this.__responsesQueue.addResponseListener("open");
    let resp = null;
    try {
      const templateFound = await auto.dashboardOpenFirstTemplate(this.__page, this.__templateName);
      assert(templateFound, "Expected template, got nothing. TIP: did you inject templates in database??")
      await this.__responsesQueue.waitUntilResponse("projects?from_template=");
      resp = await this.__responsesQueue.waitUntilResponse("open");
    }
    catch(err) {
      console.error(`"${this.__templateName}" template could not be started:\n`, err);
    }
    await this.__page.waitFor(waitFor);
    await utils.takeScreenshot(this.__page, this.__templateName + "_dashboardOpenFirstTemplate_after");
    return resp;
  }

  async waitForService(studyId, nodeId) {
    this.__responsesQueue.addResponseServiceListener(studyId, nodeId);
    let resp = null;
    try {
      resp = await this.__responsesQueue.waitUntilServiceReady(studyId, nodeId);
    }
    catch(err) {
      console.error(this.__templateName, "could not be started", err);
    }
    return resp;
  }

  async restoreIFrame() {
    await auto.restoreIFrame(this.__page);
  }

  async runPipeline(waitFor = 25000) {
    await utils.takeScreenshot(this.__page, this.__templateName + "_runStudy_before");
    await auto.runStudy(this.__page, waitFor);
    await utils.takeScreenshot(this.__page, this.__templateName + "_runStudy_after");
  }

  async openNode(nodePosInTree = 0) {
    await auto.openNode(this.__page, nodePosInTree);
    await utils.takeScreenshot(this.__page, this.__templateName + '_openNode_' + nodePosInTree);
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
    catch(err) {
      console.error(err);
    }
  }

  async retrieve(waitAfterRetrieve = 5000) {
    await auto.clickRetrieve(this.__page);
    await this.__page.waitFor(waitAfterRetrieve);
  }

  async openNodeRetrieveAndRestart(nodePosInTree = 0) {
    await utils.takeScreenshot(this.__page, "openNodeRetrieveAndRestart_before");
    await auto.openNode(this.__page, nodePosInTree);
    await this.retrieve();
    await auto.clickRestart(this.__page);
    await utils.takeScreenshot("openNodeRetrieveAndRestart_after");
  }

  async checkResults(expecedNFiles = 1) {
    await utils.takeScreenshot(this.__page, this.__templateName + "_checkResults_before");
    try {
      await auto.checkDataProducedByNode(this.__page, expecedNFiles);
    }
    catch(err) {
      console.error("Failed checking Data Produced By Node", err);
    }
    await utils.takeScreenshot(this.__page, this.__templateName + "_checkResults_after");
  }

  async removeStudy() {
    await auto.toDashboard(this.__page);
    await utils.takeScreenshot(this.__page, this.__templateName + "_dashboardDeleteFirstStudy_before");
    this.__responsesQueue.addResponseListener("projects/");
    await auto.dashboardDeleteFirstStudy(this.__page, this.__templateName);
    try {
      await this.__responsesQueue.waitUntilResponse("projects/");
    }
    catch(err) {
      console.error("Failed deleting study", err);
    }
    await utils.takeScreenshot(this.__page, this.__templateName + "_dashboardDeleteFirstStudy_after");
  }

  async logOut() {
    await auto.logOut(this.__page);
  }

  async close() {
    await this.__browser.close();
  }

  async waitFor(waitFor) {
    await this.__page.waitFor(waitFor);
  }

  async takeScreenshot(screenshotTitle) {
    await utils.takeScreenshot(this.__page, this.__templateName + '_' + screenshotTitle);
  }
}

module.exports = {
  TutorialBase
}
