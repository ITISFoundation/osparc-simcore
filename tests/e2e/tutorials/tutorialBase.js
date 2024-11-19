const assert = require('assert');

const startPuppe = require('../utils/startPuppe');
const auto = require('../utils/auto');
const utils = require('../utils/utils');
const responses = require('../utils/responsesQueue');

class TutorialBase {
  constructor(url, templateName, user, pass, newUser, basicauthuser = "", basicauthpass = "", enableDemoMode = false, parallelUserIdx = null) {
    this.__demo = enableDemoMode;
    this.__templateName = templateName;
    this.__screenshotText = templateName;
    if (parallelUserIdx) {
      this.__screenshotText + "_" + parallelUserIdx + "_";
    }

    this.__url = url;
    this.__user = user;
    this.__pass = pass;
    this.__basicauthuser = basicauthuser;
    this.__basicauthpass = basicauthpass;
    this.__newUser = newUser;

    this.__browser = null;
    this.__page = null;
    this.__responsesQueue = null;

    this.__services = null;

    this.__interval = null;

    this.__failed = false;
    this.__reasonFailed = null;

    this.startScreenshooter()
  }

  startScreenshooter() {
    try {
      utils.createScreenshotsDir();
    }
    catch (err) {
      console.error("Error: Error creating screenshots directory", err);
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
    if (this.__basicauthuser != "" && this.__basicauthpass != "") {
      await this.__page.authenticate({
        "username": this.__basicauthuser,
        "password": this.__basicauthpass
      });
    }
    this.__responsesQueue = new responses.ResponsesQueue(this.__page);

    return this.__page;
  }

  getPage() {
    return this.__page;
  }

  async __goTo() {
    console.log("Opening", this.__url);
    // Try to reach the website
    try {
      await this.__page.goto(this.__url);
    }
    catch (err) {
      console.error("Error:", this.__url, "can't be reached", err);
      throw (err);
    }
    const domain = utils.getDomain(this.__url);

    await auto.acceptCookies(this.__page);
    await auto.ignoreNewRelease(this.__page);
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

      // In case there is landing page, go to the log in page
      await auto.toLogInPage(this.__page);

      const needsRegister = await this.registerIfNeeded();
      if (!needsRegister) {
        await this.login();
      }
      await this.__printMe();
    }
    catch (err) {
      console.error("Error: Error starting", err);
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
      console.error("Error: Failed logging in", err);
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
        console.error("Error:", resource.name + " could not be fetched", err);
        throw (err);
      }
    }
  }

  getReceivedServices() {
    return this.__services;
  }

  async waitForOpen() {
    this.__responsesQueue.addResponseListener(":open");
    let resp = null;
    try {
      resp = await this.__responsesQueue.waitUntilResponse(":open");
    }
    catch (err) {
      console.error("Error:", this.__templateName, "could not be started", err);
      throw (err);
    }
    return resp;
  }

  async startClassicTIPlan() {
    await this.takeScreenshot("startClassicTIPlan_before");
    this.__responsesQueue.addResponseListener("projects?from_study=");
    this.__responsesQueue.addResponseListener(":open");
    let resp = null;
    try {
      await this.waitFor(2000);
      await auto.dashboardNewTIPlan(this.__page);
      await this.__responsesQueue.waitUntilResponse("projects?from_study=");
      resp = await this.__responsesQueue.waitUntilResponse(":open");
      const studyId = resp["data"]["uuid"];
      console.log("Study ID:", studyId);
    }
    catch (err) {
      console.error(`Error: Classic TI could not be started:\n`, err);
      throw (err);
    }
    await this.waitFor(2000);
    await this.takeScreenshot("startClassicTIPlan_after");
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
      console.error(`Error: Sim4Life Lite could not be started:\n`, err);
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
      console.error("Error:", this.__templateName, "could not be started", err);
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
      console.error(`Error: "${this.__templateName}" template could not be started:\n`, err);
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
      console.error(`Error: "${this.__templateName}" service could not be started:\n`, err);
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

  async checkNodeLogsFunctional() {
    // NOTE: logs containing [sidecar] are coming from the computational backend,
    // and are proof of backend --> RabbitMQ --> frontend connectivity
    const mustHave = "[sidecar]";
    const found = await auto.findLogMessage(this.__page, mustHave);
    if (!found) {
      throw `log message '${mustHave}' is missing from logger!`;
    }
    console.log("found logs containing '[sidecar]'");
  }

  async showLogger(show) {
    await auto.showLogger(this.__page, show);
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
      console.error("Error: open node files", err);
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
      console.error("Error: open node files", err);
      throw (err);
    }
  }

  async waitAndClick(osparcTestId, page) {
    if (page === undefined) {
      page = this.__page;
    }
    await utils.waitAndClick(page, `[osparc-test-id=${osparcTestId}]`);
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
      for (let i = 0; i < items.length; i++) {
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
        throw ("outputs folder not found");
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
      throw ("Number of files is incorrect");
    }
  }

  async checkNodeOutputs(nodePos, fileNames, openOutputsFolder = false) {
    try {
      const nodeId = await auto.openNode(this.__page, nodePos);
      await this.openNodeFiles(nodeId);
      await this.__checkNItemsInFolder(fileNames, openOutputsFolder);
    }
    catch (err) {
      console.error("Error: Checking Node Outputs:", err);
      throw (err)
    }
  }

  async checkNodeOutputsAppMode(nodeId, fileNames, openOutputsFolder = false) {
    try {
      await this.openNodeFilesAppMode(nodeId);
      await this.__checkNItemsInFolder(fileNames, openOutputsFolder);
    }
    catch (err) {
      console.error("Error: Checking Node Outputs:", err);
      throw (err)
    }
  }

  async leave(studyId) {
    if (studyId) {
      await this.toDashboard()
      await this.removeStudy(studyId);
    }
    await this.logOut();
    await this.close();
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
      console.error("Error: Failed going to dashboard", err);
      throw (err);
    }
    await this.waitFor(5000, 'Going back to Dashboard');
    await this.takeScreenshot("toDashboard_after");
  }

  async removeStudy(studyId, waitFor = 5000) {
    await auto.dashboardStudiesBrowser(this.__page);
    await this.waitFor(waitFor, 'Wait to be unlocked');
    await this.takeScreenshot("deleteFirstStudy_before");
    const intervalWait = 3000;
    try {
      const nTries = 20;
      let i
      for (i = 0; i < nTries; i++) {
        const cardUnlocked = await auto.deleteFirstStudy(this.__page, this.__templateName);
        if (cardUnlocked) {
          console.log("Study Card unlocked in " + ((waitFor + intervalWait * i) / 1000) + "s");
          break;
        }
        console.log(studyId, "study card still locked");
        await this.waitFor(intervalWait, 'Waiting in case the study was locked');
      }
    }
    catch (err) {
      console.error("Error: Failed deleting study", err);
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

  async __s4lSplashScreenOff(s4lNodeId) {
    await this.waitFor(10000, 'Wait for the s4l iframe to appear');
    await this.takeScreenshot("s4l");

    const s4lIframe = await this.getIframe(s4lNodeId);
    return new Promise(resolve => {
      s4lIframe.waitForSelector("[osparc-test-id=splash-screen-off]", {
        timeout: 60000
      })
        .then(() => resolve(true))
        .catch(() => resolve(false));
    });
  }

  async testS4L(s4lNodeId) {
    const splashScreenGone = await this.__s4lSplashScreenOff(s4lNodeId);
    if (!splashScreenGone) {
      throw ("S4L Splash Screen Timeout");
    }

    const s4lIframe = await this.getIframe(s4lNodeId);
    await this.waitAndClick('mode-button-modeling', s4lIframe);
    await this.takeScreenshot("Modeling");
    const modelTrees = await utils.getChildrenElementsBySelector(s4lIframe, '[osparc-test-id="tree-model');
    if (modelTrees.length !== 1) {
      throw ("Model tree missing");
    }

    const children = await utils.getChildrenElements(modelTrees[0]);
    const nItems = children.length;
    if (nItems > 1) {
      children[0].click();
      await this.waitFor(2000, 'Model clicked');
      await this.takeScreenshot('ModelClicked');
      children[1].click();
      await this.waitFor(2000, 'Grid clicked');
      await this.takeScreenshot('GridlClicked');
    }
  }

  async testS4LTIPostPro(s4lNodeId) {
    const splashScreenGone = await this.__s4lSplashScreenOff(s4lNodeId);
    if (!splashScreenGone) {
      throw ("S4L Splash screen Timeout");
    }

    const s4lIframe = await this.getIframe(s4lNodeId);
    await this.waitAndClick('mode-button-postro', s4lIframe);
    await this.takeScreenshot("Postpro");
    const algorithmTrees = await utils.getChildrenElementsBySelector(s4lIframe, '[osparc-test-id="tree-algorithm');
    if (algorithmTrees.length < 1) {
      throw ("Post Pro tree missing");
    }

    const children = await utils.getChildrenElements(algorithmTrees[0]);
    const nItems = children.length;
    if (nItems > 1) {
      children[0].click();
      await this.waitFor(2000, 'Importer clicked');
      await this.takeScreenshot('ImporterClicked');
      children[1].click();
      await this.waitFor(2000, 'Algorithm clicked');
      await this.takeScreenshot('AlgorithmClicked');
    }
    else {
      throw ("Post Pro tree items missing");
    }
  }

  async testS4LDipole(s4lNodeId) {
    const splashScreenGone = await this.__s4lSplashScreenOff(s4lNodeId);
    if (!splashScreenGone) {
      throw ("S4L Splash screen Timeout");
    }

    const s4lIframe = await this.getIframe(s4lNodeId);
    await this.waitAndClick('mode-button-modeling', s4lIframe);
    await this.waitAndClick('tree-model', s4lIframe);
    await this.waitFor(2000, 'Model Mode clicked');
    await this.takeScreenshot("Model");
    const modelItems = await s4lIframe.$$('.MuiTreeItem-label');
    console.log("N items in model tree:", modelItems.length / 2); // there are 2 trees

    await this.waitAndClick('mode-button-simulation', s4lIframe);
    await this.waitFor(2000, 'Simulation Mode clicked');
    await this.takeScreenshot("Simulation");

    // click on simulation root element
    const simulationsItems = await s4lIframe.$$('.MuiTreeItem-label');
    simulationsItems[0].click();
    await this.waitFor(2000, '1st item in Simulation Tree clicked');
    await this.waitAndClick('toolbar-tool-UpdateGrid', s4lIframe);
    await this.waitFor(2000, 'Updating grid...');
    await this.waitAndClick('toolbar-tool-CreateVoxels', s4lIframe);
    await this.waitFor(2000, 'Creating voxels...');
    await this.takeScreenshot("Creating voxels");
    const runButtons1 = await s4lIframe.$$('[osparc-test-id="toolbar-tool-Run"');
    await runButtons1[0].click();
    const runButtons2 = await s4lIframe.$$('[osparc-test-id="toolbar-tool-Run"');
    await runButtons2[1].click();
    await this.waitFor(2000, 'Running simulation...');
    await this.takeScreenshot("Running simulation");

    // HACK: we need to switch modes to trigger the load of the postpro tree item
    const simulationPostproSwitchTries = 100;
    for (let i = 0; i < simulationPostproSwitchTries; i++) {
      await this.waitFor(2000, 'Waiting for results');
      await this.waitAndClick('mode-button-postro', s4lIframe);
      await this.takeScreenshot("Postpro");
      const treeAlgItems = await utils.getVisibleChildrenIDs(s4lIframe, '[osparc-test-id="tree-algorithm');
      if (treeAlgItems.length) {
        await this.waitFor(2000, 'Results found');
        await this.takeScreenshot("Results found");
        break;
      }
      await this.waitAndClick('mode-button-simulation', s4lIframe);
    }
  }

  async waitForVoilaIframe(voilaNodeId) {
    const voilaTimeout = 240000;
    const checkFrequency = 5000;
    // wait for iframe to be ready, it might take a while in Voila
    let iframe = null;
    for (let i = 0; i < voilaTimeout; i += checkFrequency) {
      iframe = await this.getIframe(voilaNodeId);
      if (iframe) {
        break;
      }
      await this.waitFor(checkFrequency, `iframe not ready yet: ${i / 1000}s`);
    }
    return iframe;
  }

  async waitForVoilaRendered(iframe) {
    // Voila says: "Ok, voila is still executing..."
    await this.waitFor(10000);

    const voilaRenderTimeout = 120000;
    const checkFrequency = 2000;
    // wait for iframe to be rendered
    for (let i = 0; i < voilaRenderTimeout; i += checkFrequency) {
      if (await utils.isElementVisible(iframe, '#rendered_cells')) {
        console.log("Voila rendered")
        return true;
      }
      await this.waitFor(checkFrequency, `iframe not rendered yet: ${i / 1000}s`);
    }
    return false;
  }

  async testSARValidation(sarNodeId) {
    // SAR Validation service testing
    await this.waitFor(15000, 'SAR Service started');
    await this.takeScreenshot("testSARValidation_before");

    this.__responsesQueue.addResponseListener("training-set-generation/generate");
    this.__responsesQueue.addResponseListener("training-set-generation/data");
    this.__responsesQueue.addResponseListener("training-set-generation/distribution", false);
    try {
      const sarIframe = await this.getIframe(sarNodeId);
      await this.waitAndClick("createTrainingSetBtn", sarIframe);
      await this.__responsesQueue.waitUntilResponse("training-set-generation/generate");
      await this.__responsesQueue.waitUntilResponse("training-set-generation/data");
      await this.__responsesQueue.waitUntilResponse("training-set-generation/distribution");
    }
    catch (err) {
      console.error("Error:", this.__templateName, "training-set can't be generated", err);
      throw (err);
    }

    this.__responsesQueue.addResponseListener("training-set-generation/xport", false);
    try {
      const sarIframe = await this.getIframe(sarNodeId);
      await this.waitAndClick("exportTrainingSetBtn", sarIframe);
      await this.__responsesQueue.waitUntilResponse("training-set-generation/xport");
    }
    catch (err) {
      console.error("Error:", this.__templateName, "training-set can't be exported", err);
      throw (err);
    }

    await this.takeScreenshot("testSARValidation_after");
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

  getTutorialFailedReason() {
    return this.__reasonFailed;
  }

  async setTutorialFailed(reason = "") {
    this.__failed = true;
    this.__reasonFailed = reason
  }
}

module.exports = {
  TutorialBase
}
