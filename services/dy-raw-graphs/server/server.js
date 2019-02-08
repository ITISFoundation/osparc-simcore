/* global require */
/* global console */
/* eslint no-console: "off" */

// #run script:
// node server.js

const express = require('express');

const app = express();
let server = require('http').createServer(app);
let routes = require('./routes');
const config = require('./config');

console.log(`received basepath: ${config.BASEPATH}`);
// serve static assets normally
console.log('Serving static : ' + config.APP_PATH);
app.use(`${config.BASEPATH}`, express.static(config.APP_PATH));


// init route for retrieving port inputs
app.use(`${config.BASEPATH}`, routes);

// start server
server.listen(config.PORT, config.HOSTNAME);
console.log('server started on ' + config.HOSTNAME + ':' + config.PORT);

