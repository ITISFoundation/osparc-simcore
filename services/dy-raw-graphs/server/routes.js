/* global require */
/* global console */
/* global module */
/* eslint no-console: "off" */

let express = require('express');
const path = require('path');
let appRouter = express.Router();
const events = require('events');
const config = require('./config');
const fs = require('fs');
const spawn = require("child_process").spawn;

let eventEmitter = new events.EventEmitter()

appRouter.use(express.json())

// handle every other route with index.html, which will contain
// a script tag to your application's JavaScript file(s).
appRouter.get('/', function (request, response) {
  console.log('Routing / to ' + path.resolve(config.APP_PATH, 'index.html'));
  response.sendFile(path.resolve(config.APP_PATH, 'index.html'));
});

appRouter.get('/retrieve', callInputRetriever);
appRouter.get('/input', getInputFile);
appRouter.get('/inputs', getInputFiles);
appRouter.get('/output', getOutput);
appRouter.put('/output', setOutput);

module.exports = appRouter;


function callInputRetriever(request, response) {
  console.log('Received a call to retrieve the data on input ports from ' + request.ip);

  var pyProcess = spawn("python3", ["/home/scu/server/input-retriever.py"]);

  pyProcess.on("error", (err) => {
    console.log(`ERROR: ${err}`);
    response.sendStatus("500");
  });

  pyProcess.stdout.setEncoding("utf8");
  pyProcess.stdout.on("data", (data) => {
    console.log(`stdout: ${data}`);
  });

  pyProcess.stderr.on("data", (data) => {
    console.log(`stderr: ${data}`);
  });

  pyProcess.on("close", (code) => {
    console.log(`Function completed with code ${code}.`);
    if (code === 0) {
      response.sendStatus("200");
      console.log("All went fine");
    }
    else {
      response.sendStatus("500");
      console.log(code, ":(");
    }
  });
}

function getInputDir() {
  const inputsDir = '../inputs/';
  if (!fs.existsSync(inputsDir)) {
    fs.mkdirSync(inputsDir);
  }
  return inputsDir;
}

function getOutputDir() {
  const outputsDir = '../outputs/';
  if (!fs.existsSync(outputsDir)) {
    fs.mkdirSync(outputsDir);
  }
  const port = "output_1/";
  const outputsDirPort = outputsDir + port;
  if (!fs.existsSync(outputsDirPort)) {
    fs.mkdirSync(outputsDirPort);
  }
  return outputsDirPort;
}

function getInputFile(request, response) {
  const inputsDir = getInputDir();
  const fileName = inputsDir + request.query["fileName"];
  console.log('getInputFile', fileName);
  fs.readFile(fileName, (err, data) => {
    if (err) {
      console.error(err);
      response.sendStatus("500");
      return;
    }
    response.send(data);
  });
}

function getInputFiles(request, response) {
  console.log('getInputFiles');
  const inputsDir = getInputDir();
  fs.readdir(inputsDir, (err, files) => {
    if (err) {
      console.error(err);
      response.sendStatus("500");
      return;
    }
    let metadata = [];
    for (let i=0; i<files.length; i++) {
      if (fs.lstatSync(inputsDir+files[i]).isFile()) {
        metadata.push({
          title: files[i],
          type: 'Other',
          url: files[i]
        });
      }
    }
    response.send(metadata);
  });
}

function addViewBoxAttr(svgCode) {
  // get width value and replace it by 'auto'
  let width = svgCode.match(/"(.*?)"/);
  if (width) {
    width = width[1];
    svgCode = svgCode.replace(/width="(.*?)"/,"width='auto'");
  }

  // get height value and replace it by 'auto'
  let height = svgCode.match(/"(.*?)"/);
  if (height) {
    for (let i=0; i<height.length; i++) {
      console.log("height_"+i, height[i]);
    }
    height = height[1];
    svgCode = svgCode.replace(/height="(.*?)"/,"height='auto'");
  }

  // add viewBox attribute right after svg tag
  const viewBoxStr = " viewBox='0 0 "+width+" " +height+ "'";
  console.log(viewBoxStr);
  svgCode = svgCode.slice(0, 4) + viewBoxStr + svgCode.slice(4);

  return svgCode;
}

function setOutput(request, response) {
  console.log('setOutput');
  const outputsDirPort = getOutputDir();
  const outputFileName = outputsDirPort + "output.svg";
  let svgCode = request.body.svgCode;
  svgCode = addViewBoxAttr(svgCode);
  fs.writeFile(outputFileName, svgCode, err => {
    if (err) {
      console.log(err);
      response.sendStatus("500");
      return;
    }
    console.log("The file was saved!");
    response.send({
      status: "ok"
    });
  });
}

function getOutput(request, response) {
  console.log('getOutput');
  const outputsDirPort = getOutputDir();
  fs.readdir(outputsDirPort, (err, files) => {
    if (err) {
      console.log(err);
      response.sendStatus("500");
      return;
    }
    if (files.length > 0) {
      const fileName = outputsDirPort + files[0];
      fs.readFile(fileName, (err, data) => {
        if (err) {
          console.log(err);
          response.sendStatus("500");
          return;
        }
        const cont = data.toString();
        response.send(cont);
      });
    } else {
      console.log('outdir is empty');
      response.sendStatus("204");
    }
  });
}


module.exports.eventEmitter = eventEmitter;
