/* global require */
/* global console */
/* global module */
/* global process */
/* global __dirname */
/* eslint no-console: "off" */

let express = require("express");
const spawn = require("child_process").spawn;
const path = require('path');
let appRouter = express.Router();
const events = require('events');

const APP_PATH = process.env.SIMCORE_WEB_OUTDIR || path.resolve(__dirname, 'source-output');
let eventEmitter = new events.EventEmitter()

// handle every other route with index.html, which will contain
// a script tag to your application's JavaScript file(s).
appRouter.get('/', function (request, response) {
  console.log('Routing / to ' + path.resolve(APP_PATH, 'index.html'));
  response.sendFile(path.resolve(APP_PATH, 'index.html'));
});

appRouter.get('/retrieve', callInputRetriever);

module.exports = appRouter;

function callInputRetriever(request, response) {
  console.log('Received a call to retrieve the data on input ports from ' + request.ip);

  var pyProcess = spawn("python", ["/home/node/source/input-retriever.py"]);

  pyProcess.on("error", function (err) {
    console.log(`ERROR: ${err}`);
    response.sendStatus("500");
  });

  let dataString = "";
  pyProcess.stdout.setEncoding("utf8");
  pyProcess.stdout.on("data", function (data) {
    console.log(`stdout: ${data}`);
    dataString += data;
  });

  pyProcess.stderr.on("data", function (data) {
    console.log(`stderr: ${data}`);
  });

  pyProcess.on("close", function (code) {
    console.log(`Function completed with code ${code}.`);
    if (code !== 0) {
      response.sendStatus("500");
    }
    else {
      const dataArray = dataString.split("json=");
      if (dataArray.length == 2) {
        console.log(`retrieved data ${dataArray[1]}`)
        // we have some data in json format
        const data = JSON.parse(dataArray[1]);
        const modelName = data.model_name.value;
        console.log(`model to be loaded is ${modelName}`)        
        eventEmitter.emit("retrieveModel", modelName);
      }
      response.sendStatus("204");
    }
  });
}

module.exports.eventEmitter = eventEmitter;