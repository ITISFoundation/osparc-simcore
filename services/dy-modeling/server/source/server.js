/* global require */
/* global console */
/* eslint no-console: "off" */

// #run script:
// node server.js

const express = require('express');

const app = express();
let server = require('http').createServer(app);
let Promise = require('promise');
let sizeof = require('object-sizeof');
let s4l_utils = require('./s4l_utils');
let routes = require('./routes');
const config = require('./config');

console.log(`received basepath: ${config.BASEPATH}`);
// serve static assets normally
console.log('Serving static : ' + config.APP_PATH);
app.use(`${config.BASEPATH}`, express.static(config.APP_PATH));


// init route for retrieving port inputs
app.use(`${config.BASEPATH}`, routes);
routes.eventEmitter.on("retrieveModel", function(modelName){
  s4l_utils.connectToS4LServer().then(function () {
    importModelS4L(modelName);
  }).catch(failureCallback);
});
// start server
server.listen(config.PORT, config.HOSTNAME);
console.log('server started on ' + config.PORT + '/app');

// init socket.io
let io = require('socket.io')(server, {
  pingInterval: 15000,
  pingTimeout: 60000,
  path: `${config.BASEPATH}/socket.io`,
});
let connectedClient = null;

// Socket IO stuff
io.on('connection', socketIOConnected);

// init thrift
s4l_utils.connectToS4LServer().catch(function(err) {
  console.log(`no connection to S4L: ${err}`);
});


function socketIOConnected(socketClient) {
  console.log(`Client connected as ${socketClient.id}...`);
  connectedClient = socketClient;
  signalEndOfTransmission(); // ensure the client is not waiting infinely in case of reconnection

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
    s4l_utils.connectToS4LServer()
      .then(function () {
        return createSplineS4L(pointList, uuid);
      })
  });

  socketClient.on('newSphereS4LRequested', function (radiusCenterUUID) {
    let radius = radiusCenterUUID[0];
    let center = radiusCenterUUID[1];
    let uuid = radiusCenterUUID[2];
    s4l_utils.connectToS4LServer()
      .then(function () {
        return createSphereS4L(radius, center, uuid);
      }).catch(failureCallback);
  });

  socketClient.on('newBooleanOperationRequested', function (entityMeshesSceneOperationType) {
    let entityMeshesScene = entityMeshesSceneOperationType[0];
    let operationType = entityMeshesSceneOperationType[1];
    s4l_utils.connectToS4LServer().then(function () {
      booleanOperationS4L(entityMeshesScene, operationType);
    }).catch(failureCallback);
  });
}


// S4L (thrift) stuff -----------------------------------------------------------------------------
async function failureCallback(error) {
  console.log('Thrift error: ' + error);
  await signalEndOfTransmission(); // ensure this gets called in case of failure
}

async function importModelS4L(modelName) {
  try {
    await signalStartTransmission();
    await s4l_utils.loadModelInS4L(modelName);
    const solid_entities = await s4l_utils.getEntitiesFromS4L(s4l_utils.entityType.SOLID_BODY_AND_MESH);
    const splineEntities = await s4l_utils.getEntitiesFromS4L(s4l_utils.entityType.WIRE);
    const numberEntities = solid_entities.length + splineEntities.length;
    await signalInitiateProgress(numberEntities);
    await transmitEntities(solid_entities);
    await transmitSplines(splineEntities);    
    await signalEndOfTransmission();
  } 
  catch (error) {
    console.log(`Error while importing model: ${error}`);
  }
}

async function transmitSplines(splineEntities) {
  let totalTransmittedMB = 0;
  for (let splineIndex = 0; splineIndex < splineEntities.length; splineIndex++) {
    const wireObject = await s4l_utils.getWireFromS4l(splineEntities[splineIndex]);
    const transmittedBytes = await transmitSpline(wireObject);
    totalTransmittedMB += transmittedBytes / (1024.0 * 1024.0);
    await signalIncrementProgress();
  }
  console.log(`Sent all spline objects: ${totalTransmittedMB}MB`);
}
function transmitSpline(wireObject) {
  return new Promise(function (resolve, reject) {
    if (!connectedClient) {
      console.log("no client...");
      reject("no connected client");
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
    const transmittedBytes = await transmitScene(encodedScene);
    totalTransmittedMB += transmittedBytes / (1024.0 * 1024.0);
    await signalIncrementProgress();
  }
  console.log(`Sent all GLTF scene: ${totalTransmittedMB}MB`);
}

function signalStartTransmission() {
  return new Promise(function (resolve, reject) {
    if (!connectedClient) {
      console.log("no client...");
      reject("no connected client");
    }
    console.log(`signaling client that transfer is starting...`);
    connectedClient.emit('transmissionStarts', function() {
      console.log(`received OK from client`);
      resolve();
    })
  });
}

function signalInitiateProgress(total) {
  return new Promise(function (resolve, reject) {
    if (!connectedClient) {
      console.log("no client...");
      reject("no connected client");
    }
    connectedClient.emit('initiateProgress', total, function() {
      resolve();
    })
  });
}

function signalIncrementProgress(value =1) {
  return new Promise(function (resolve, reject) {
    if (!connectedClient) {
      console.log("no client...");
      reject("no connected client");
    }
    connectedClient.emit('incrementProgress', value, function() {
      resolve();
    })
  });
}

function signalEndOfTransmission() {
  return new Promise(function (resolve, reject) {
    if (!connectedClient) {
      console.log("no client...");
      reject("no connected client");
    }
    console.log(`signaling client that transfer is complete`);
    connectedClient.emit('transmissionCompleted', function() {
      console.log(`received OK from client`);
      resolve();
    })
  });
}

function transmitScene(scene) {
  return new Promise(function (resolve, reject) {
    if (!connectedClient) {
      console.log("no client...");
      reject("no connected client");
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

async function booleanOperationS4L(entityMeshesScene, operationType) {
  console.log('server: booleanOps4l ' + operationType);
  await signalStartTransmission();
  await s4l_utils.newDocumentS4L();
  const uuidsList = await s4l_utils.sendEncodedSceneToS4L(entityMeshesScene);
  const newEntityUuid = await s4l_utils.booleanOperationS4L(uuidsList, operationType);
  const listOfEntities = await s4l_utils.getEntitiesFromS4L(s4l_utils.entityType.MESH);
  const index = listOfEntities.findIndex(function (element) {
    return element.uuid == newEntityUuid;
  });
  await transmitEntities([listOfEntities[index]]);  
  await signalEndOfTransmission();
}

async function createSphereS4L(radius, center, uuid) {
  await signalStartTransmission();
  await s4l_utils.newDocumentS4L();
  const newEntityUuid = await s4l_utils.createSphereS4L(radius, center, uuid);
  const listOfEntities = await s4l_utils.getEntitiesFromS4L(s4l_utils.entityType.MESH);
  const index = listOfEntities.findIndex(function (element) {
    return element.uuid == newEntityUuid;
  });
  await transmitEntities([listOfEntities[index]]);  
  await signalEndOfTransmission();
}

async function createSplineS4L(pointList, uuid) {
  await signalStartTransmission();
  await s4l_utils.newDocumentS4L();
  const newEntityUuid = await s4l_utils.createSplineS4L(pointList, uuid);
  const listOfEntities = await s4l_utils.getEntitiesFromS4L(s4l_utils.entityType.WIRE);
  const index = listOfEntities.findIndex(function (element) {
    return element.uuid == newEntityUuid;
  });
  await transmitSplines([listOfEntities[index]]);
  await signalEndOfTransmission();
}

// generic functions --------------------------------------------------
function importScene(socketClient, activeUser) {
  const modelsDirectory = config.APP_PATH + config.MODELS_PATH + activeUser;
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
  const modelsDirectory = config.APP_PATH + config.MODELS_PATH + activeUser + '/myScene.gltf';
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
