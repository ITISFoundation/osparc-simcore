/* global require */
/* global console */
/* global module */
/* eslint no-console: "off" */

let express = require('express');
const path = require('path');
let appRouter = express.Router();
const events = require('events');
const config = require('./config');
const fs = require('fs')

let eventEmitter = new events.EventEmitter()

// handle every other route with index.html, which will contain
// a script tag to your application's JavaScript file(s).
appRouter.get('/', function (request, response) {
  console.log('Routing / to ' + path.resolve(config.APP_PATH, 'index.html'));
  response.sendFile(path.resolve(config.APP_PATH, 'index.html'));
});

appRouter.get('/inputs', getInputFiles);

appRouter.get('/input', getInputFile);

appRouter.get('/retrieve', callInputRetriever);

module.exports = appRouter;

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

function callInputRetriever(request, response) {
  console.log('Received a call to retrieve the data on input ports from ' + request.ip);
}

module.exports.eventEmitter = eventEmitter;