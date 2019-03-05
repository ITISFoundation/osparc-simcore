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

appRouter.get('/input', getInputFile);

appRouter.get('/inputs', getInputFiles);

appRouter.get('/retrieve', callInputRetriever);

appRouter.get('/output', getOutput);
appRouter.put('/output', setOutput);

module.exports = appRouter;

function getInputFile(request, response) {
  const inputsDir = '../inputs/';
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
  const inputsDir = '../inputs/';
  fs.readdir(inputsDir, (err, files) => {
    if (err) {
      console.error(err);
      response.sendStatus("500");
      return;
    }
    let metadata = [];
    for (let i=0; i<files.length; i++) {
      metadata.push({
        title: files[i],
        type: 'Other',
        url: files[i]
      });
    }
    response.send(metadata);
  });
}

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

function setOutput(request, response) {
  console.log('setOutput');
  const outputsDir = '../outputs/';
  if (!fs.existsSync(outputsDir)) {
    fs.mkdirSync(outputsDir);
  }
  const outputFileName = outputsDir + "output.svg";
  const svgCode = request.body.svgCode;
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
  const outputsDir = '../outputs/';
  fs.readdir(outputsDir, (err, files) => {
    if (err) {
      console.log(err);
      response.sendStatus("500");
      return;
    }
    if (files.length > 0) {
      const fileName = outputsDir + files[0];
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
    }
  });
}


module.exports.eventEmitter = eventEmitter;
