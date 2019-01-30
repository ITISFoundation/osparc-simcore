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

// handle every other route with index.html, which will contain
// a script tag to your application's JavaScript file(s).
appRouter.get('/', function (request, response) {
  console.log('Routing / to ' + path.resolve(config.APP_PATH, 'index.html'));
  response.sendFile(path.resolve(config.APP_PATH, 'index.html'));
});

appRouter.get('/input', getInputFile);

appRouter.get('/inputs', getInputFiles);

appRouter.get('/retrieve', callInputRetriever);

module.exports = appRouter;

function getInputFile(request, response) {
  const fileName = request.query["fileName"]
  console.log('getInputFile', fileName);
  fs.readFile(fileName, (err, data) => {
    if (err) {
      console.error(err);
      return;
    }
    response.send(data);
  });
}

function getInputFiles(request, response) {
  console.log('getInputFiles');
  const inputsDir = '../inputs/'
  fs.readdir(inputsDir, (err, files) => {
    if (err) {
      console.error(err);
      return;
    }
    let metadata = [];
    for (let i=0; i<files.length; i++) {
      metadata.push({
        title: files[i],
        type: 'Other',
        url: inputsDir + files[i]
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
      console.log("All went fine");
    }
    else {
      response.sendStatus("500");
      console.log(code, ":(");
    }
  });
}

module.exports.eventEmitter = eventEmitter;