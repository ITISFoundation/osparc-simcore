/* global require */
/* global process */
/* global __dirname */
/* global console */
/* eslint no-console: "off" */

// #run script:
// node server.js

const express = require('express');
const path = require('path');

const app = express();
let server = require('http').createServer(app);
let Promise = require('promise');
let sizeof = require('object-sizeof');
let s4l_utils = require('./s4l_utils');

// constants ---------------------------------------------
const HOSTNAME = process.env.SIMCORE_WEB_HOSTNAME || '127.0.0.1';
const PORT = process.env.SIMCORE_WEB_PORT || 8080;
const BASEPATH = process.env.SIMCORE_NODE_BASEPATH;
const APP_PATH = process.env.SIMCORE_WEB_OUTDIR || path.resolve(__dirname, 'source-output');
const MODELS_PATH = '/models/';

const staticPath = APP_PATH;


// variables ----------------------------------------
console.log(BASEPATH);
// serve static assets normally
console.log('Serving static : ' + staticPath);
app.use(`${BASEPATH}`, express.static(staticPath));


// init route for retrieving port inputs
app.use(`${BASEPATH}`, require("./routes"));
// start server
server.listen(PORT, HOSTNAME);
console.log('server started on ' + PORT + '/app');

// init socket.io
let io = require('socket.io')(server);
let connectedClient = null;

// Socket IO stuff
io.on('connection', function (socketClient) {
  console.log(`Client connected as ${socketClient.id}...`);
  connectedClient = socketClient;

  socketClient.on('disconnecting', function (reason) {
    console.log(`Client disconnecteding with reason ${reason}`);
  });

  socketClient.on('disconnect', function (reason) {
    console.log(`Client disconnected with reason ${reason}`);
    connectedClient = null;
  });

  socketClient.on('error', function (error) {
    console.log(`socket error: ${error}`);
  });

  socketClient.on('importScene', function (activeUser) {
    importScene(socketClient, activeUser);
  });

  socketClient.on('exportScene', function (args) {
    let activeUser = args[0];
    let sceneJson = args[1];
    exportScene(socketClient, activeUser, sceneJson);
  });

  socketClient.on('importModel', function (modelName) {
    s4l_utils.connectToS4LServer().then(function () {
      importModelS4L(modelName);
    }).catch(failureCallback);
  });

  socketClient.on('newSplineS4LRequested', function (pointListUUID) {
    var pointList = pointListUUID[0];
    var uuid = pointListUUID[1];
    s4l_utils.connectToS4LServer().then(function () {
      createSplineS4L(socketClient, pointList, uuid);
    }).catch(failureCallback);
  });

  socketClient.on('newSphereS4LRequested', function (radiusCenterUUID) {
    let radius = radiusCenterUUID[0];
    let center = radiusCenterUUID[1];
    let uuid = radiusCenterUUID[2];
    s4l_utils.connectToS4LServer()
      .then(function () {
        console.log('calling createSpheres4L');
        return s4l_utils.createSphereS4L(radius, center, uuid);
      })
      .then(function (uuid) {
        console.log('calling get entity meshes' + uuid);
        return s4l_utils.getEntityMeshes(uuid, 'newSphereS4LRequested');
      })
      .then(function (meshEntity) {
        console.log('emitting back ' + meshEntity.value);
        socketClient.emit('newSphereS4LRequested', meshEntity);
      })
      .catch(failureCallback);
  });

  socketClient.on('newBooleanOperationRequested', function (entityMeshesSceneOperationType) {
    let entityMeshesScene = entityMeshesSceneOperationType[0];
    let operationType = entityMeshesSceneOperationType[1];
    s4l_utils.connectToS4LServer().then(function () {
      booleanOperationS4L(socketClient, entityMeshesScene, operationType);
    }).
      catch(failureCallback);
  });
});

// init thrift
s4l_utils.connectToS4LServer().catch(console.log("no connection to S4L"));

// TODO: these should be moved to s4l utils
// S4L (thrift) stuff -----------------------------------------------------------------------------
function failureCallback(error) {
  console.log('Thrift error: ' + error);
}
function createSplineS4L(socketClient, pointList, uuid) {
  let transform4x4 = [
    1.0, 0.0, 0.0, 0.0,
    0.0, 1.0, 0.0, 0.0,
    0.0, 0.0, 1.0, 0.0,
    0.0, 0.0, 0.0, 1.0];
  let color = {
    diffuse: {
      r: 1.0,
      g: 0.3,
      b: 0.65,
      a: 1.0
    }
  };
  let spline = {
    vertices: pointList,
    transform4x4: transform4x4,
    material: color
  };
  s4l_utils.s4lModelerClient.CreateSpline(spline, uuid, function (err, responseUUID) {
    s4l_utils.s4lModelerClient.GetEntityWire(responseUUID, function (err2, response2) {
      let listOfPoints = {
        type: 'newSplineS4LRequested',
        value: response2,
        uuid: responseUUID,
      };
      socketClient.emit('newSplineS4LRequested', listOfPoints);
    });
  });
}

async function importModelS4L(modelName) {
  await s4l_utils.loadModelInS4L(modelName);
  const solid_entities = await s4l_utils.getEntitiesFromS4L(s4l_utils.thrModelerTypes.EntityFilterType.SOLID_BODY_AND_MESH);
  const totalTransmittedMB = await transmitEntities(solid_entities);
  console.log(`Sent all GLTF scene: ${totalTransmittedMB}MB`);
  const splineEntities = await s4l_utils.getEntitiesFromS4L(s4l_utils.thrModelerTypes.EntityFilterType.WIRE);
  const totalTransmittedSplineMB = await transmitSplines(splineEntities);
  console.log(`Sent all GLTF scene: ${totalTransmittedSplineMB}MB`);
}

async function transmitSplines(splineEntities) {
  let totalTransmittedMB = 0;
  for (let splineIndex = 0; splineIndex < splineEntities.length; splineIndex++) {
    const wireObject = await s4l_utils.getWireFromS4l(splineEntities[splineIndex]);
    const transmittedBytes = await transmitSpline(wireObject);
    totalTransmittedMB += transmittedBytes/(1024.0*1024.0);
  }
  return totalTransmittedMB;
}
function transmitSpline(wireObject) {
  return new Promise(function(resolve, reject){
    if (!connectedClient) {
      console.log("no client...");
      reject();
    }
    const sceneSizeBytes = sizeof(wireObject);
    console.log(`sending ${wireObject.value.length} points of size ${sceneSizeBytes} to client...`);
    connectedClient.binary(true).emit('newSplineS4LRequested', wireObject, function () {
      // callback fct from client after receiving data
      console.log(`received acknowledgment from client`);
      resolve(sceneSizeBytes);
    });
  });
}

async function transmitEntities(entities) {
  let totalTransmittedMB = 0;
  for (let i = 0; i < entities.length; i++) {
    const encodedScene = await s4l_utils.getEncodedSceneFromS4L(entities[i]);
    const transmittedBytes = await sendEncodedSceneToClient(encodedScene);
    totalTransmittedMB += transmittedBytes/(1024.0*1024.0);
  }
  return totalTransmittedMB;
}

function sendEncodedSceneToClient(scene) {
  return new Promise(function(resolve, reject) {
    if (!connectedClient) {
      console.log("no client...");
      reject();
    }
    const sceneSizeBytes = sizeof(scene);
    console.log(`sending scene ${sceneSizeBytes} to client...`);
    connectedClient.binary(true).emit('importModelScene', scene, function () {
      // callback fct from client after receiving data
      console.log(`received acknowledgment from client`);
      resolve(sceneSizeBytes);
    });
  });
}

async function booleanOperationS4L(socketClient, entityMeshesScene, operationType) {  
  console.log('server: booleanOps4l ' + operationType);
  await s4l_utils.newDocumentS4L();
  let uuidsList = await s4l_utils.sendEncodedSceneToS4L(entityMeshesScene);
  let newEntityUuid = await s4l_utils.booleanOperationS4L(uuidsList);
  let encodedScene = await s4l_utils.getEncodedSceneFromS4L(newEntityUuid);
  console.log("sending scene to client..");
  socketClient.emit('newBooleanOperationRequested', encodedScene);
}

// generic functions --------------------------------------------------
function importScene(socketClient, activeUser) {
  const modelsDirectory = APP_PATH + MODELS_PATH + activeUser;
  console.log('import Scene from: ', modelsDirectory);
  let fs = require('fs');
  fs.readdirSync(modelsDirectory).forEach((file) => {
    const filePath = modelsDirectory + '/' + file;
    if (file === 'myScene.gltf') {
      fs.readFile(filePath, function (err, data) {
        if (err) {
          throw err;
        }
        let modelJson = {};
        modelJson.modelName = file;
        modelJson.value = data.toString();
        modelJson.type = 'importScene';
        console.log('sending file: ', modelJson.modelName);
        socketClient.emit('importScene', modelJson);
      });
    }
  });
}

function exportScene(socketClient, activeUser, sceneJson) {
  const modelsDirectory = APP_PATH + MODELS_PATH + activeUser + '/myScene.gltf';
  console.log('export Scene to: ', modelsDirectory);
  let content = JSON.stringify(sceneJson);
  let fs = require('fs');
  fs.writeFile(modelsDirectory, content, 'utf8', function (err) {
    let response = {};
    response.type = 'exportScene';
    response.value = false;
    if (err) {
      console.log('Error: ', err);
    }
    else {
      console.log(modelsDirectory, ' file was saved!');
      response.value = true;
    }
    socketClient.emit('exportScene', response);
    if (err) {
      throw err;
    }
  });
}

// GET retrieve method route -------------------------------------------------
