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

const HOSTNAME = process.env.SIMCORE_WEB_HOSTNAME || '127.0.0.1';
const PORT = process.env.SIMCORE_WEB_PORT || 8080;
const APP_PATH = process.env.SIMCORE_WEB_OUTDIR || path.resolve(__dirname, 'source-output');
const MODELS_PATH = '/models/';


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


let thrift = require('thrift');

let thrApplication = require('./thrift/ApplicationJSNode/gen-nodejs/Application.js');
// let thrApplicationTypes = require('./thrift/ApplicationJSNode/gen-nodejs/application_types');
// let thrAppLogger = require('./thrift/ApplicationJSNode/gen-nodejs/Logger');
// let thrAppSharedService = require('./thrift/ApplicationJSNode/gen-nodejs/SharedService');
// let thrAppProcessFactory = require('./thrift/ApplicationJSNode/gen-nodejs/ProcessFactory');
let thrModeler = require('./thrift/ModelerJSNode/gen-nodejs/Modeler');
let thrModelerTypes = require('./thrift/ModelerJSNode/gen-nodejs/modeler_types');

const S4L_IP = process.env.CS_S4L_HOSTNAME || '172.16.9.89';
const S4L_PORT_APP = process.env.CS_S4L_PORT_APP || 9095;
const S4L_PORT_MOD = process.env.CS_S4L_PORT_MOD || 9096;

const transport = thrift.TBufferedTransport;
const protocol = thrift.TBinaryProtocol;

let s4lAppClient = null;
let s4lModelerClient = null;
connectToS4LServer().then(function() {
  console.log('Connected to S4L server');
  s4lAppClient.GetApiVersion( function(err, response) {
    console.log('Application API version', response);
  });
  s4lModelerClient.GetApiVersion( function(err, response) {
    console.log('Application API version', response);
  });
}).catch(function(err) {
  console.log('No connection: ' + err);
});


let io = require('socket.io')(server);
io.on('connection', function(socketClient) {
  console.log('Client connected...');

  socketClient.on('importScene', function(activeUser) {
    importScene(socketClient, activeUser);
  });

  socketClient.on('exportScene', function(args) {
    let activeUser = args[0];
    let sceneJson = args[1];
    exportScene(socketClient, activeUser, sceneJson);
  });

  socketClient.on('importModel', function(modelName) {
    connectToS4LServer().then(function() {
      importModelS4L(socketClient, modelName);
    }).catch(failureCallback);
  });


  socketClient.on('newSplineS4LRequested', function(pointListUUID) {
    var pointList = pointListUUID[0];
    var uuid = pointListUUID[1];
    connectToS4LServer().then(function() {
      createSplineS4L(socketClient, pointList, uuid);
    }).catch(failureCallback);
  });

  socketClient.on('newSphereS4LRequested', function(radiusCenterUUID) {
    let radius = radiusCenterUUID[0];
    let center = radiusCenterUUID[1];
    let uuid = radiusCenterUUID[2];
    connectToS4LServer()
      .then(function() {
        console.log('calling createSpheres4L');
        return createSphereS4L(radius, center, uuid);
      })
      .then(function(uuid) {
        console.log('calling get entity meshes' + uuid);
        return getEntityMeshes(uuid, 'newSphereS4LRequested');
      })
      .then(function(meshEntity) {
        console.log('emitting back ' + meshEntity.value);
        socketClient.emit('newSphereS4LRequested', meshEntity);
      })
      .catch(failureCallback);
  });

  socketClient.on('newBooleanOperationRequested', function(entityMeshesSceneOperationType) {
    let entityMeshesScene = entityMeshesSceneOperationType[0];
    let operationType = entityMeshesSceneOperationType[1];
    connectToS4LServer().then(function() {
      booleanOperationS4L(socketClient, entityMeshesScene, operationType);
    }).
      catch(failureCallback);
  });
});

function failureCallback(error) {
  console.log('Thrift error: ' + error);
}

function connectToS4LServer() {
  return new Promise(function(resolve, reject) {
    createThriftConnection(S4L_IP, S4L_PORT_APP, thrApplication, s4lAppClient, disconnectFromApplicationServer)
      .then(function(client) {
        s4lAppClient = client;
        createThriftConnection(S4L_IP, S4L_PORT_MOD, thrModeler, s4lModelerClient, disconnectFromModelerServer)
          .then(function(client) {
            s4lModelerClient = client;
            resolve();
          });
      })
      .catch(function(err) {
        reject(err);
      });
  });
}

function disconnectFromModelerServer() {
  s4lModelerClient = null;
  console.log('Modeler client disconnected');
}

function disconnectFromApplicationServer() {
  s4lAppClient = null;
  console.log('Application client disconnected');
}

/**
 * creates a Thrift connection with the thing object
 *
 * @param {any} host
 * @param {any} port
 * @param {any} thing
 * @param {any} client
 * @param {any} disconnectionCB
 * @return {any} the client object promise
 */
function createThriftConnection(host, port, thing, client, disconnectionCB) {
  return new Promise(function(resolve, reject) {
    if (client == null) {
      const connection = thrift.createConnection(host, port, {
        transport: transport,
        protocol: protocol,
      });

      connection.on('close', function() {
        console.log('Connection to ' + host + ':' + port + ' closed');
        disconnectionCB();
      });
      connection.on('timeout', function() {
        console.log('Connection to ' + ' timed out...');
      });
      connection.on('reconnecting', function(delay, attempt) {
        console.log('Reconnecting to ' + host + ':' + port + ' delay ' + delay + ', attempt ' + attempt);
      });
      connection.on('connect', function() {
        console.log('connected to ' + host + ':' + port);
        client = thrift.createClient(thing, connection);
        resolve(client);
      });
      connection.on('error', function(err) {
        console.log('connection error to ' + host + ':' + port);
        reject(err);
      });
    }
    else {
      resolve(client);
    }
  });
}

function createSphereS4L(radius, center, uuid) {  
  return new Promise(function(resolve, reject) {
    s4lModelerClient.CreateSolidSphere( center, radius, uuid, function(err, responseUUID) {
      if (err) {
        reject(err);
      }
      else {
        resolve(uuid);
      }
    });
  });
}

function getEntityMeshes(uuid, valueType) {
  return new Promise(function(resolve, reject) {
    const getNormals = false;
    s4lModelerClient.GetEntityMeshes( uuid, getNormals, function(err2, response2) {
      if (err2) {
        reject(err2);
      }
      let meshEntity = {
        type: valueType,
        value: response2,
        uuid: uuid,
      };
      resolve(meshEntity);
    });
  });
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
  s4lModelerClient.CreateSpline( spline, uuid, function(err, responseUUID) {
    s4lModelerClient.GetEntityWire( responseUUID, function(err2, response2) {
      let listOfPoints = {
        type: 'newSplineS4LRequested',
        value: response2,
        uuid: responseUUID,
      };
      socketClient.emit('newSplineS4LRequested', listOfPoints);
    });
  });
}

function importScene(socketClient, activeUser) {
  const modelsDirectory = APP_PATH + MODELS_PATH + activeUser;
  console.log('import Scene from: ', modelsDirectory);
  let fs = require('fs');
  fs.readdirSync(modelsDirectory).forEach((file) => {
    const filePath = modelsDirectory +'/'+ file;
    if (file === 'myScene.gltf') {
      fs.readFile(filePath, function(err, data) {
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
  fs.writeFile(modelsDirectory, content, 'utf8', function(err) {
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

function importModelS4L(socketClient, modelName) {
  const data_path = 'c:/app/data/';
  s4lAppClient.NewDocument( function(err, response) {
    let modelPath = data_path;
    switch (modelName) {
    case 'Thelonious':
      modelPath += 'thelonius_reduced.smash';
      break;
    case 'Rat':
      modelPath += 'ratmodel_simplified.smash';
      break;
    case 'BigRat':
      modelPath += 'Rat_Male_567g_v2.0b02.sat';
      break;
    case 'DecDemo_Modeler.smash':
    case 'DecDemo_LF.smash':
      modelPath += modelName;
      break;
    default:
      modelPath += 'ratmodel_simplified.smash';
      break;
    }
    console.log('Importing', modelName);
    s4lModelerClient.ImportModel( modelPath, function(err2, response2) {
      console.log('Importing path', modelPath);
      s4lModelerClient.GetFilteredEntities(thrModelerTypes.EntityFilterType.BODY_AND_MESH,
        function(err3, response3) {
          console.log('Total meshes', response3.length);

          let nMeshes = response3.length;
          for (let i = 0; i <nMeshes; i++) {
            let meshId = response3[i].uuid;
            s4lModelerClient.GetEntitiesEncodedScene([meshId], thrModelerTypes.SceneFileFormat.GLTF,
              function(err4, response4) {
                let encodedScene = {
                  type: 'importModelScene',
                  value: response4.data,
                };
                let storeAllInServerFirst = false;
                if (storeAllInServerFirst) {
                  let listOfEncodedScenes = [];
                  listOfEncodedScenes.push(encodedScene);
                  // socketClient.emit('importModelScene', meshEntity);
                  console.log(i);
                  if (i === nMeshes-1) {
                    sendEncodedScenesToTheClient(socketClient, listOfEncodedScenes);
                  }
                }
                else {
                  sendEncodedScenesToTheClient(socketClient, [encodedScene]);
                }
              });
          }
        });
    });
  });

  function sendEncodedScenesToTheClient(socketClient, listOfEncodedScenes) {
    for (let i = 0; i < listOfEncodedScenes.length; i++) {
      socketClient.emit('importModelScene', listOfEncodedScenes[i]);
    }
  }
}

function booleanOperationS4L(socketClient, entityMeshesScene, operationType) {
  let myEncodedScene = {
    fileType: thrModelerTypes.SceneFileFormat.GLTF,
    data: entityMeshesScene,
  };
  console.log('server: booleanOps4l ' + operationType);
  s4lAppClient.NewDocument( function(err, response) {
    if (err) {
      console.log('New Document creation failed ' + err);
    }
    else {
      s4lModelerClient.CreateEntitiesFromScene(myEncodedScene, function(err, response) {
        if (err) {
          console.log('Entities creation failed: ' + err);
        }
        else {
          s4lModelerClient.BooleanOperation(response, operationType, function(err2, response2) {
            if (err2) {
              console.log('Boolean operation failed: ' + err2);
            }
            else {
              s4lModelerClient.GetEntitiesEncodedScene([response2], thrModelerTypes.SceneFileFormat.GLTF,
                function(err3, response3) {
                  if (err3) {
                    console.log('Getting entities failed: ' + err3);
                  }
                  else {
                    let encodedScene = {
                      type: 'newBooleanOperationRequested',
                      value: response3.data,
                    };
                    socketClient.emit('newBooleanOperationRequested', encodedScene);
                  }
                });
            }
          });
        }
      });
    }
  });
}


console.log('server started on ' + PORT + '/app');
