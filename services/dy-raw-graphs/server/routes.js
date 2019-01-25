/* global require */
/* global console */
/* global module */
/* eslint no-console: "off" */

let express = require('express');
const path = require('path');
let appRouter = express.Router();
const events = require('events');
const config = require('./config');

let eventEmitter = new events.EventEmitter()

// handle every other route with index.html, which will contain
// a script tag to your application's JavaScript file(s).
appRouter.get('/', function (request, response) {
  console.log('Routing / to ' + path.resolve(config.APP_PATH, 'index.html'));
  response.sendFile(path.resolve(config.APP_PATH, 'index.html'));
});

appRouter.get('/retrieve', callInputRetriever);

module.exports = appRouter;

function callInputRetriever(request, response) {
  console.log('Received a call to retrieve the data on input ports from ' + request.ip);
}

module.exports.eventEmitter = eventEmitter;