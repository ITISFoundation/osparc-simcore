// node SarValidation.js [url_prefix] [template_uuid] [timeout] [--demo]
// node SarValidation.js --url [full_url] [timeout] [--demo]

// master https://osparc-master.speag.com/study/2b7b88be-ea51-11ed-ade4-02420a000d13
// prod https://sarvalidation.site (redirects to https://osparc.io/study/ff72c36a-df81-11ed-9c9e-02420a0b755a)

const tutorialBase = require('../tutorials/tutorialBase');
const utils = require('../utils/utils');

const args = process.argv.slice(2);
const urlIdx = args.indexOf('--url'); // used in production only

let anonURL, startTimeout, enableDemoMode;

if (urlIdx > -1) {
  anonURL = args[urlIdx + 1];
  startTimeout = args[urlIdx + 2];
  enableDemoMode = args.includes("--demo");
} else {
  const parsed = utils.parseCommandLineArgumentsAnonymous(args);
  anonURL = parsed.urlPrefix + parsed.templateUuid;
  startTimeout = parsed.startTimeout;
  enableDemoMode = parsed.enableDemoMode;
}

const screenshotPrefix = "SarValidation";


async function runTutorial () {
  const tutorial = new tutorialBase.TutorialBase(anonURL, screenshotPrefix, null, null, null, "", "", enableDemoMode);

  try {
    await tutorial.beforeScript();
    const studyResp = await tutorial.openStudyLink();
    const studyData = studyResp["data"];
    const studyId = studyData["uuid"];

    const sarNodeId = utils.getNodeIdFromServiceKey(studyData["workbench"], "iec62209-web");
    if (!sarNodeId) {
      throw new Error('Could not find node with service key "iec62209-web"');
    }
    await tutorial.waitForServices(
      studyId,
      [sarNodeId],
      startTimeout,
      false
    );

    await tutorial.testSARValidation(sarNodeId);
  }
  catch(err) {
    await tutorial.setTutorialFailed();
    console.log('Tutorial error: ' + err);
  }
  finally {
    await tutorial.logOut();
    await tutorial.close();
  }

  if (tutorial.getTutorialFailed()) {
    throw "Tutorial Failed";
  }
}

runTutorial()
  .catch(error => {
    console.log('Puppeteer error: ' + error);
    process.exit(1);
  });
