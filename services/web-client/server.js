// #run script:
// node server.js

const express = require('express');
const path = require('path');

const app = express();
let server = require('http').createServer(app);
let Promise = require('promise');

const HOSTNAME = process.env.SIMCORE_WEB_HOSTNAME || '127.0.0.1';
const PORT = process.env.SIMCORE_WEB_PORT || 8080;
const APP_PATH = process.env.SIMCORE_WEB_OUTDIR || path.resolve(__dirname, 'source-output');


// serve static assets normally
const staticPath = APP_PATH;
console.log( 'Serving static : ' + staticPath );
app.use( express.static(staticPath) );

// handle every other route with index.html, which will contain
// a script tag to your application's JavaScript file(s).
app.get('/', function(request, response) {
  console.log('Routing / to ' + path.resolve(APP_PATH, 'index.html'));
  response.sendFile( path.resolve(APP_PATH, 'index.html') );
});

server.listen(PORT, HOSTNAME);

let io = require('socket.io')(server);
io.on('connection', function(socketClient) {
  console.log('Client connected...');
});

function failureCallback(error) {
  console.log('Thrift error: ' + error);
}

console.log('server started on ' + PORT + '/app');
