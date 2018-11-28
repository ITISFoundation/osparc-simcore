/* global require */
/* global console */
/* global module */
/* eslint no-console: "off" */

const config = require('./config');
let Promise = require('promise');
let thrift = require('thrift');
let thrApplication = require('./thrift/ApplicationJSNode/gen-nodejs/Application.js');
// let thrApplicationTypes = require('./thrift/ApplicationJSNode/gen-nodejs/application_types');
// let thrAppLogger = require('./thrift/ApplicationJSNode/gen-nodejs/Logger');
// let thrAppSharedService = require('./thrift/ApplicationJSNode/gen-nodejs/SharedService');
// let thrAppProcessFactory = require('./thrift/ApplicationJSNode/gen-nodejs/ProcessFactory');
let thrModeler = require('./thrift/ModelerJSNode/gen-nodejs/Modeler');
let thrModelerTypes = require('./thrift/ModelerJSNode/gen-nodejs/modeler_types');
let sizeof = require('object-sizeof');
const transport = thrift.TBufferedTransport;
const protocol = thrift.TBinaryProtocol;

let s4lAppClient = null;
let s4lModelerClient = null;

async function connectToS4LServer() {
  try {
    s4lAppClient = await createThriftConnection(config.S4L_IP, config.S4L_PORT_APP, thrApplication, s4lAppClient, disconnectFromApplicationServer);  
    s4lAppClient.GetApiVersion(function (err, response) {
      if (err) {
        console.log(`error getting application api version: ${err}`);
        throw new Error(`error retrieving api`);
      }
      else {
        console.log('Application API version', response);
      }    
    });
    s4lModelerClient = await createThriftConnection(config.S4L_IP, config.S4L_PORT_MOD, thrModeler, s4lModelerClient, disconnectFromModelerServer);
    s4lModelerClient.GetApiVersion(function (err, response) {
      if (err) {
        console.log(`error getting modeler api version: ${err}`);
        throw new Error(`error retrieving api`);
      }
      else {
        console.log('Modeler API version', response);
      }    
    });
  } catch (error) {
    console.log(`Error while connecting to S4L: ${error}`);
    throw error;
  }  
}

function createThriftConnection(host, port, thing, client, disconnectionCB) {
  return new Promise(function (resolve, reject) {
    if (client == null) {
      const connection = thrift.createConnection(host, port, {
        transport: transport,
        protocol: protocol,
      });

      connection.on('close', function () {
        console.log('Thrit: Connection to ' + host + ':' + port + ' closed');
        disconnectionCB();
      });
      connection.on('timeout', function () {
        console.log('Thrit: Connection to ' + ' timed out...');
      });
      connection.on('reconnecting', function (delay, attempt) {
        console.log('Thrit: Reconnecting to ' + host + ':' + port + ' delay ' + delay + ', attempt ' + attempt);
      });
      connection.on('connect', function () {
        console.log('Thrit: connected to ' + host + ':' + port);
        client = thrift.createClient(thing, connection);
        console.log('Thrift: client created ' + client);
        resolve(client);
      });
      connection.on('error', function (err) {
        console.log('Thrit: connection error to ' + host + ':' + port);
        reject(err);
      });
    }
    else {
      resolve(client);
    }
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

function createSphereS4L(radius, center, uuid) {
  return new Promise(function (resolve, reject) {
    s4lModelerClient.CreateSolidSphere(center, radius, uuid, function (err, responseUUID) {
      if (err) {
        reject(err);
      }
      else {
        resolve(responseUUID);
      }
    });
  });
}
function createSplineS4L(pointList, uuid) {
  return new Promise(function (resolve, reject) {
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
    s4lModelerClient.CreateSpline(spline, uuid, function (err, responseUUID) {
      if (err) {
        reject(err);
      }
      else {
        resolve(responseUUID);
      }
    });
  });
}

function getEntityMeshes(uuid, valueType) {
  return new Promise(function (resolve, reject) {
    const getNormals = false;
    s4lModelerClient.GetEntityMeshes(uuid, getNormals, function (err2, response2) {
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

function getWireFromS4l(entity) {
  return new Promise(function(resolve, reject) {
    s4lModelerClient.GetEntityWire(entity.uuid, function(err, wirePoints) {
      if (err) {
        console.log(`error while getting wire: ${err}`)
        reject(err);
      }
      else {
        console.log(`received wire of ${wirePoints.length} points`);
        let wireObject = {
          type: 'newSplineS4LRequested',
          value: wirePoints,
          uuid: entity.uuid,
          name: entity.name,
          pathNames: entity.pathNames,
          pathUuids: entity.pathUuids,
          color: entity.color,
        };
        resolve(wireObject);
      }
    });
  });
}

function loadModelInS4L(modelName) {
  return new Promise(function(resolve, reject){
    s4lAppClient.NewDocument(function(){
      let modelPath = config.S4L_DATA_PATH + modelName;
      console.log('Importing', modelPath);
      s4lModelerClient.ImportModel(modelPath, function(err){
        if (err) {
          console.log(`loading in S4L failed with ${err}`)
          reject(err);
        }
        else {
          console.log("loading in S4L done")
          resolve();
        }          
      });
    });
  });
}

function getEntitiesFromS4L(entityType) {
  return new Promise(function(resolve, reject){
    console.log(`retrieving entities of type: ${entityType}`);
    s4lModelerClient.GetFilteredEntities(entityType,
      function (err, entities) {
        if (err) {
          console.log(`error while retrieving entities ${err}`)
          reject(err);
        }
        else {
          console.log(`received ${entities.length} entities`)
          resolve(entities);
        }
      });
  });    
}

function getEncodedSceneFromS4L(entity) {
  return new Promise(function(resolve, reject) {
    s4lModelerClient.GetEntitiesEncodedScene([entity.uuid], thrModelerTypes.SceneFileFormat.GLTF,
      function (err, scene) {
        if (err) {
          console.log(`error while getting encoded scene: ${err}`)
          reject(err);
        }
        else {
          console.log(`received scene of ${sizeof(scene)} bytes`);
          let encodedScene = {
            type: 'importModelScene',
            value: scene.data,
            path: entity.path,
            uuid: entity.uuid,
            name: entity.name,
            pathNames: entity.pathNames,
            pathUuids: entity.pathUuids,
          };
          resolve(encodedScene);
        }
      })
  });
}

function sendEncodedSceneToS4L(encodedScene) {
  return new Promise(function(resolve, reject) {
    if (!s4lModelerClient) {
      reject("no modeler client");
    }
    let myEncodedScene = {
      fileType: thrModelerTypes.SceneFileFormat.GLTF,
      data: encodedScene,
    };
    s4lModelerClient.CreateEntitiesFromScene(myEncodedScene, function (err, response) {
      if (err) {
        console.log('Entities creation failed: ' + err);
        reject(err);
      }
      else {
        console.log(`scene created with response: ${response}`);
        resolve(response);
      }
    });
  });
}

function newDocumentS4L() {
  return new Promise(function(resolve, reject) {
    if (!s4lAppClient) {
      reject("no app client");
    }
    s4lAppClient.NewDocument(function (err, response) {
      if (err) {
        console.log('New Document creation failed ' + err);
        reject(err);
      }
      else {
        console.log(`New Document created: ${response}`);
        resolve(response);
      }      
    });
  });
}

function booleanOperationS4L(uuidsList, operationType) {
  return new Promise(function(resolve, reject) {
    if (!s4lModelerClient) {
      console.log(`no modeler client`);
      reject("no modeler client");
    }
    console.log(`starting boolean operation with ${uuidsList}`);
    s4lModelerClient.BooleanOperation(uuidsList, operationType, function (err, response) {
      console.log(`completed operation...`);
      if (err) {
        console.log('Entities creation failed: ' + err);
        reject(err);
      }
      else {
        console.log(`boolean operation completed created with response: ${response}`);
        resolve(response);
      }
    });
  });
}

module.exports.connectToS4LServer = connectToS4LServer;

module.exports.newDocumentS4L = newDocumentS4L;
module.exports.loadModelInS4L = loadModelInS4L;

module.exports.getEncodedSceneFromS4L = getEncodedSceneFromS4L;
module.exports.sendEncodedSceneToS4L = sendEncodedSceneToS4L;

module.exports.createSphereS4L = createSphereS4L;
module.exports.createSplineS4L = createSplineS4L;
module.exports.booleanOperationS4L = booleanOperationS4L;

module.exports.getEntitiesFromS4L = getEntitiesFromS4L;
module.exports.getEntityMeshesFromS4L = getEntityMeshes;
module.exports.getWireFromS4l = getWireFromS4l;

module.exports.entityType = thrModelerTypes.EntityFilterType;
module.exports.booleanOperationType = thrModelerTypes.BooleanOperationType;