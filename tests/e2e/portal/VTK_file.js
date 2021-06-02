// node VTK_file.js [url] [file_type] [viewer_key] [viewer_vs] [download_link] [file_name] [file_size] [--demo]

const tutorialBase = require('../tutorials/tutorialBase');
const utils = require('../utils/utils');

const args = process.argv.slice(2);
const {
  urlPrefix,
  params,
  enableDemoMode
} = utils.parseCommandLineArgumentsStudyDispatcherParams(args);

let anonURL = urlPrefix + "/view";
for (let i=0; i<Object.keys(params).length; i++) {
  const paramKey =  Object.keys(params)[i];
  const paramValue =  params[paramKey];
  i==0 ? anonURL += "?" : anonURL += "&";
  anonURL += paramKey + "=" + paramValue
}
const screenshotPrefix = "VTK_file_";


async function runTutorial () {
  const tutorial = new tutorialBase.TutorialBase(anonURL, screenshotPrefix, null, null, null, enableDemoMode);

  try {
    tutorial.startScreenshooter();
    const page = await tutorial.beforeScript();
    const studyData = await tutorial.openStudyLink();
    const studyId = studyData["data"]["uuid"];
    console.log("Study ID:", studyId);

    const workbenchData = utils.extractWorkbenchData(studyData["data"]);
    const nodeIdViewer = workbenchData["nodeIds"][1];
    await tutorial.waitForServices(workbenchData["studyId"], [nodeIdViewer]);

    // Some time for starting the service
    await tutorial.waitFor(10000);
    await utils.takeScreenshot(page, screenshotPrefix + 'service_started');

    const iframeHandles = await page.$$("iframe");
    const iframes = [];
    for (let i=0; i<iframeHandles.length; i++) {
      const frame = await iframeHandles[i].contentFrame();
      iframes.push(frame);
    }
    // url/x/nodeIdViewer
    const frame = iframes.find(iframe => iframe._url.includes(nodeIdViewer));

    // inside the iFrame, click on doscument icon on top
    const docSelector = 'body > div > div > div.MainView-topBar_4t9p4 > div.MainView-title_2sz83 > div.MainView-menu_37qbe > div.ToggleIcons-container_4prdd > div:nth-child(1) > i.ToggleIcons-openFileButtonActive_3q2p5.ToggleIcons-openFileButton_3bz5y.ToggleIcons-button_2phh8.font-awesome-fa_4nxvz.font-awesome-fa-fw_vg4ef.font-awesome-fa-file-text-o_3dsxg.ToggleIcons-activeButton_3cj9s';
    await frame.waitForSelector(docSelector);
    await frame.click(docSelector);
    await tutorial.waitFor(2000);
    await utils.takeScreenshot(page, screenshotPrefix + 'iFrame1');
  }
  catch(err) {
    tutorial.setTutorialFailed(true);
    console.log('Tutorial error: ' + err);
  }
  finally {
    tutorial.stopScreenshooter();
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
