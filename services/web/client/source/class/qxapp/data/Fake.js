/**
 *  Collection of free function with fake data for testing
 *
 * TODO: Use faker https://scotch.io/tutorials/generate-fake-data-for-your-javascript-applications-using-faker
 */

/* global window */

qx.Class.define("qxapp.data.Fake", {
  type: "static",

  statics: {

    /**
     * Represents an empty project descriptor
    */
    NEW_PROJECT_DESCRIPTOR: qx.data.marshal.Json.createModel({
      name: "New Project",
      description: "Empty",
      thumbnail: "https://imgplaceholder.com/171x96/cccccc/757575/ion-plus-round",
      created: null,
      prjId: null
    }),

    getUsername: function() {
      return "bizzy";
    },

    getS3PublicBucketName: function() {
      return "simcore";
    },

    getObjectList: function() {
      const objects = [
        {
          "path": "simcore0/file0",
          "lastModified": "blah",
          "size": 10
        }, {
          "path": "simcore0/bat/two/three/four/file1",
          "lastModified": "blah",
          "size": 11
        }, {
          "path": "simcore/file2",
          "lastModified": "blah",
          "size": 12
        }, {
          "path": "simcore/file3",
          "lastModified": "blah",
          "size": 13
        }, {
          "path": "simcore2/file4",
          "lastModified": "blah2",
          "size": 14
        }, {
          "path": "simcore2/file5",
          "lastModified": "blah2",
          "size": 15
        }, {
          "path": "simcore0/one/file6",
          "lastModified": "blah",
          "size": 16
        }, {
          "path": "simcore0/one/two/three/four/file7",
          "lastModified": "blah",
          "size": 17
        }
      ];
      return objects;
    },

    /**
     * Returns a qx array with projects associated to a user
     */
    getUserProjects: function(count = 3, username = "bizzy") {
      let rawData = [];

      for (var i = 0; i < count; i++) {
        var item = qx.data.marshal.Json.createModel({
          name: "Project #" + (i + 1),
          description: "This is a short description by " + username,
          thumbnail: null,
          created: null,
          prjId: null
        });
        rawData.push(item);
      }

      // A wrapper around raw array to make it "bindable"
      var data = new qx.data.Array(rawData);
      return data;
    },

    getTemplateProjects: function() {
      let rawData = [];

      let item1 = qx.data.marshal.Json.createModel({
        name: "Sleepers",
        description: "Sample used for the unidirectional pipelining",
        thumbnail: null,
        created: null,
        prjId: "temp1"
      });
      rawData.push(item1);

      let item2 = qx.data.marshal.Json.createModel({
        name: "Single Cell",
        description: "Colleen Clancy use case",
        thumbnail: null,
        created: null,
        prjId: "temp2"
      });
      rawData.push(item2);

      // A wrapper around raw array to make it "bindable"
      var data = new qx.data.Array(rawData);
      return data;
    },

    getPrjData: function(prjId) {
      switch (prjId) {
        case "temp1": {
          let tempData = this.getTemp1Data();
          return tempData;
        }
        case "temp2": {
          let tempData = this.getTemp2Data();
          return tempData;
        }
      }
      return null;
    },

    getTemp1Data: function() {
      const nNodes = 8;
      let nodeIds = [];
      for (let i=0; i<nNodes; i++) {
        nodeIds.push(qxapp.utils.Utils.uuidv4());
      }

      let temp1Data = {
        "nodes": [{
          "uuid": nodeIds[0],
          "key": "simcore/services/comp/itis/sleeper",
          "name": "Sleeper 1",
          "tag": "0.0.1",
          "authors": [{
            "name": "Somebody",
            "email": "somebody@itis.ethz.ch",
            "affiliation": "ITIS Foundation"
          }],
          "contact": "somebody@itis.ethz.ch",
          "description": "Solver that sleeps for a random amount of seconds",
          "position": {
            "x": 50,
            "y": 100
          },
          "inputs": [{
            "key": "in_1",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "file-url",
            "value": null
          }, {
            "key": "in_2",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "integer",
            "value": 2
          }],
          "outputs": [{
            "key": "out_1",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "file-url",
            "value": null
          }, {
            "key": "out_2",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "integer",
            "value": null
          }],
          "settings": []
        }, {
          "uuid": nodeIds[1],
          "key": "simcore/services/comp/itis/sleeper",
          "name": "Sleeper 2",
          "tag": "0.0.1",
          "authors": [{
            "name": "Somebody",
            "email": "somebody@itis.ethz.ch",
            "affiliation": "ITIS Foundation"
          }],
          "contact": "somebody@itis.ethz.ch",
          "description": "Solver that sleeps for a random amount of seconds",
          "position": {
            "x": 50,
            "y": 300
          },
          "inputs": [{
            "key": "in_1",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "file-url",
            "value": null
          }, {
            "key": "in_2",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "integer",
            "value": 2
          }],
          "outputs": [{
            "key": "out_1",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "file-url",
            "value": null
          }, {
            "key": "out_2",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "integer",
            "value": null
          }],
          "settings": []
        }, {
          "uuid": nodeIds[2],
          "key": "simcore/services/comp/itis/sleeper",
          "name": "Sleeper 3",
          "tag": "0.0.1",
          "authors": [{
            "name": "Somebody",
            "email": "somebody@itis.ethz.ch",
            "affiliation": "ITIS Foundation"
          }],
          "contact": "somebody@itis.ethz.ch",
          "description": "Solver that sleeps for a random amount of seconds",
          "position": {
            "x": 300,
            "y": 100
          },
          "inputs": [{
            "key": "in_1",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "file-url",
            "value": null
          }, {
            "key": "in_2",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "integer",
            "value": 2
          }],
          "outputs": [{
            "key": "out_1",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "file-url",
            "value": null
          }, {
            "key": "out_2",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "integer",
            "value": null
          }],
          "settings": []
        }, {
          "uuid": nodeIds[3],
          "key": "simcore/services/comp/itis/sleeper",
          "name": "Sleeper 4",
          "tag": "0.0.1",
          "authors": [{
            "name": "Somebody",
            "email": "somebody@itis.ethz.ch",
            "affiliation": "ITIS Foundation"
          }],
          "contact": "somebody@itis.ethz.ch",
          "description": "Solver that sleeps for a random amount of seconds",
          "position": {
            "x": 300,
            "y": 300
          },
          "inputs": [{
            "key": "in_1",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "file-url",
            "value": null
          }, {
            "key": "in_2",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "integer",
            "value": 2
          }],
          "outputs": [{
            "key": "out_1",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "file-url",
            "value": null
          }, {
            "key": "out_2",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "integer",
            "value": null
          }],
          "settings": []
        }, {
          "uuid": nodeIds[4],
          "key": "simcore/services/comp/itis/sleeper",
          "name": "Sleeper 5",
          "tag": "0.0.1",
          "authors": [{
            "name": "Somebody",
            "email": "somebody@itis.ethz.ch",
            "affiliation": "ITIS Foundation"
          }],
          "contact": "somebody@itis.ethz.ch",
          "description": "Solver that sleeps for a random amount of seconds",
          "position": {
            "x": 550,
            "y": 200
          },
          "inputs": [{
            "key": "in_1",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "file-url",
            "value": null
          }, {
            "key": "in_2",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "integer",
            "value": 2
          }],
          "outputs": [{
            "key": "out_1",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "file-url",
            "value": null
          }, {
            "key": "out_2",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "integer",
            "value": null
          }],
          "settings": []
        }, {
          "uuid": nodeIds[5],
          "key": "simcore/services/comp/itis/sleeper",
          "name": "Sleeper 6",
          "tag": "0.0.1",
          "authors": [{
            "name": "Somebody",
            "email": "somebody@itis.ethz.ch",
            "affiliation": "ITIS Foundation"
          }],
          "contact": "somebody@itis.ethz.ch",
          "description": "Solver that sleeps for a random amount of seconds",
          "position": {
            "x": 800,
            "y": 100
          },
          "inputs": [{
            "key": "in_1",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "file-url",
            "value": null
          }, {
            "key": "in_2",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "integer",
            "value": 2
          }],
          "outputs": [{
            "key": "out_1",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "file-url",
            "value": null
          }, {
            "key": "out_2",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "integer",
            "value": null
          }],
          "settings": []
        }, {
          "uuid": nodeIds[6],
          "key": "simcore/services/comp/itis/sleeper",
          "name": "Sleeper 7",
          "tag": "0.0.1",
          "authors": [{
            "name": "Somebody",
            "email": "somebody@itis.ethz.ch",
            "affiliation": "ITIS Foundation"
          }],
          "contact": "somebody@itis.ethz.ch",
          "description": "Solver that sleeps for a random amount of seconds",
          "position": {
            "x": 800,
            "y": 300
          },
          "inputs": [{
            "key": "in_1",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "file-url",
            "value": null
          }, {
            "key": "in_2",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "integer",
            "value": 2
          }],
          "outputs": [{
            "key": "out_1",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "file-url",
            "value": null
          }, {
            "key": "out_2",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "integer",
            "value": null
          }],
          "settings": []
        }, {
          "uuid": nodeIds[7],
          "key": "simcore/services/comp/itis/sleeper",
          "name": "Sleeper 8",
          "tag": "0.0.1",
          "authors": [{
            "name": "Somebody",
            "email": "somebody@itis.ethz.ch",
            "affiliation": "ITIS Foundation"
          }],
          "contact": "somebody@itis.ethz.ch",
          "description": "Solver that sleeps for a random amount of seconds",
          "position": {
            "x": 1050,
            "y": 200
          },
          "inputs": [{
            "key": "in_1",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "file-url",
            "value": null
          }, {
            "key": "in_2",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "integer",
            "value": 2
          }],
          "outputs": [{
            "key": "out_1",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "file-url",
            "value": null
          }, {
            "key": "out_2",
            "label": "Number of seconds to sleep",
            "desc": "Number of seconds to sleep",
            "type": "integer",
            "value": null
          }],
          "settings": []
        }],
        "links": [{
          "uuid": qxapp.utils.Utils.uuidv4(),
          "node1Id": nodeIds[0],
          "port1Id": "out_1",
          "node2Id": nodeIds[2],
          "port2Id": "in_1"
        }, {
          "uuid": qxapp.utils.Utils.uuidv4(),
          "node1Id": nodeIds[0],
          "port1Id": "out_2",
          "node2Id": nodeIds[2],
          "port2Id": "in_2"
        }, {
          "uuid": qxapp.utils.Utils.uuidv4(),
          "node1Id": nodeIds[1],
          "port1Id": "out_1",
          "node2Id": nodeIds[3],
          "port2Id": "in_1"
        }, {
          "uuid": qxapp.utils.Utils.uuidv4(),
          "node1Id": nodeIds[1],
          "port1Id": "out_2",
          "node2Id": nodeIds[3],
          "port2Id": "in_2"
        }, {
          "uuid": qxapp.utils.Utils.uuidv4(),
          "node1Id": nodeIds[2],
          "port1Id": "out_1",
          "node2Id": nodeIds[4],
          "port2Id": "in_1"
        }, {
          "uuid": qxapp.utils.Utils.uuidv4(),
          "node1Id": nodeIds[3],
          "port1Id": "out_2",
          "node2Id": nodeIds[4],
          "port2Id": "in_2"
        }, {
          "uuid": qxapp.utils.Utils.uuidv4(),
          "node1Id": nodeIds[4],
          "port1Id": "out_1",
          "node2Id": nodeIds[5],
          "port2Id": "in_1"
        }, {
          "uuid": qxapp.utils.Utils.uuidv4(),
          "node1Id": nodeIds[4],
          "port1Id": "out_2",
          "node2Id": nodeIds[6],
          "port2Id": "in_2"
        }, {
          "uuid": qxapp.utils.Utils.uuidv4(),
          "node1Id": nodeIds[5],
          "port1Id": "out_1",
          "node2Id": nodeIds[7],
          "port2Id": "in_1"
        }, {
          "uuid": qxapp.utils.Utils.uuidv4(),
          "node1Id": nodeIds[6],
          "port1Id": "out_2",
          "node2Id": nodeIds[7],
          "port2Id": "in_2"
        }]
      };
      return temp1Data;
    },

    getTemp2Data: function() {
      const nNodes = 3;
      let nodeIds = [];
      for (let i=0; i<nNodes; i++) {
        nodeIds.push(qxapp.utils.Utils.uuidv4());
      }

      let temp2Data = {
        "nodes": [{
          "uuid": nodeIds[0],
          "key": "FileManager",
          "name": "File Manager",
          "tag": "0.0.1",
          "description": "File Manager",
          "authors": [{
            "name": "Somebody",
            "email": "somebody@itis.ethz.ch",
            "affiliation": "ITIS Foundation"
          }],
          "contact": "somebody@itis.ethz.ch",
          "position": {
            "x": 50,
            "y": 100
          },
          "inputs": [],
          "outputs": [{
            "key": "out_1",
            "label": "File-url",
            "description": "File-url",
            "type": "file-url",
            "defaultValue": null
          }],
          "settings": []
        }, {
          "uuid": nodeIds[1],
          "key": "simcore/services/comp/ucdavis/cardiac-singlecell",
          "name": "DBP-Clancy-Rabbit-Single-Cell solver v 0.0.2",
          "tag": "0.0.1",
          "description": "Single cell solver for DBP-Clancy-Rabbit model",
          "authors": [{
            "name": "John Doe",
            "email": "j.doe@ua.com",
            "affiliation": "University of Anywhere, Department of something"
          }],
          "contact": "j.doe@ua.com",
          "position": {
            "x": 350,
            "y": 100
          },
          "inputs": [{
            "key": "Na",
            "label": "Na blocker drug concentration",
            "desc": "Set Na blocker drug concentration",
            "type": "number",
            "value": 0.0
          }, {
            "key": "Kr",
            "label": "Kr blocker drug concentration",
            "desc": "Set Kr blocker drug concentration",
            "type": "number",
            "value": 0.0
          }, {
            "key": "BCL",
            "label": "Basic Cycle Length (BCL)",
            "desc": "Set Basic Cycle Length (BCL)",
            "type": "integer",
            "value": 200
          }, {
            "key": "NBeats",
            "label": "Number of beats",
            "desc": "Set Number of beats",
            "type": "integer",
            "value": 5
          }, {
            "key": "Ligand",
            "label": "Ligand concentration",
            "desc": "Set Ligand concentration ",
            "type": "number",
            "value": 0.0
          }, {
            "key": "cAMKII",
            "label": "Adjust cAMKII activity levels",
            "desc": "Adjust cAMKII activity levels (expression = WT, OE, or KO)",
            "type": "string",
            "value": "WT"
          }, {
            "key": "initial_WTstates.txt",
            "label": "Intitial variables file ",
            "desc": "Initial variables file corresponding to SS_rabbit_varNames.txt",
            "type": "file-url",
            "value": null
          }],
          "outputs": [{
            "key": "Allresult_1Hz.txt",
            "label": "All results",
            "desc": "All results",
            "type": "file-url",
            "value": null
          }, {
            "key": "apds_1Hz.txt",
            "label": "apds",
            "desc": "apds",
            "type": "file-url",
            "value": null
          }, {
            "key": "finalStates.txt",
            "label": "finalStates",
            "desc": "finalStates",
            "type": "file-url",
            "value": null
          }, {
            "key": "vm_1Hz.txt",
            "label": "vm",
            "desc": "vm",
            "type": "file-url",
            "value": null
          }],
          "settings": []
        }, {
          "uuid": nodeIds[2],
          "key": "simcore/services/dynamic/cc-0d-viewer",
          "name": "cc-0d-viewer",
          "tag": "0.0.1",
          "description": "Graph viewer for data generated by cc-0d solver",
          "authors": [{
            "name": "Somebody",
            "email": "somebody@itis.ethz.ch",
            "affiliation": "ITIS Foundation"
          }],
          "contact": "somebody@itis.ethz.ch",
          "position": {
            "x": 700,
            "y": 100
          },
          "inputs": [{
            "key": "in_1",
            "label": "vm 1Hz",
            "desc": "Computed values from the solver",
            "type": "file-url",
            "value": "null"
          }, {
            "key": "in_2",
            "label": "all results 1Hz",
            "desc": "Computed values from the solver",
            "type": "file-url",
            "value": "null"
          }],
          "outputs": [],
          "settings": [],
          "viewer": {
            "ip":null,
            "port":null
          }
        }],
        "links": [{
          "uuid": qxapp.utils.Utils.uuidv4(),
          "node1Id": nodeIds[0],
          "port1Id": "out_1",
          "node2Id": nodeIds[1],
          "port2Id": "initial_WTstates.txt"
        }, {
          "uuid": qxapp.utils.Utils.uuidv4(),
          "node1Id": nodeIds[1],
          "port1Id": "vm_1Hz.txt",
          "node2Id": nodeIds[2],
          "port2Id": "in_1"
        }, {
          "uuid": qxapp.utils.Utils.uuidv4(),
          "node1Id": nodeIds[1],
          "port1Id": "Allresult_1Hz.txt",
          "node2Id": nodeIds[2],
          "port2Id": "in_2"
        }]
      };
      return temp2Data;
    },

    getFakeServices: function() {
      let fakeServices = [];
      Array.prototype.push.apply(fakeServices, qxapp.data.Fake.getProducers());
      Array.prototype.push.apply(fakeServices, qxapp.data.Fake.getComputationals());
      Array.prototype.push.apply(fakeServices, qxapp.data.Fake.getAnalyses());
      return fakeServices;
    },

    getProducers: function() {
      const producers = [{
        "key": "modeler",
        "tag": "1.0",
        "name": "Modeler",
        "description": "Modeler",
        "inputs": [{
          "key": "in_1",
          "label": "ViPModel",
          "description": "Select ViP Model",
          "type": "string",
          "defaultValue": "rat",
          "widget": "selectBox",
          "cfg": {
            structure: [
              {
                key: "rat",
                label: "Rat"
              },
              {
                key: "sphere",
                label: "Sphere"
              }
            ]
          }
        }],
        "outputs": [{
          "key": "out_1",
          "label": "Scene",
          "description": "Scene",
          "type": "scene",
          "defaultValue": null
        }],
        "settings": [],
        "viewer": {
          "ip": "http://" + window.location.hostname,
          "port": null
        }
      }, {
        "key": "RandomNumberGeneratorID",
        "tag": "1.0",
        "name": "Random Number Generator",
        "description": "Random Number Generator",
        "inputs": [{
          "key": "in_1",
          "label": "Number Min",
          "description": "Number Min",
          "type": "integer",
          "defaultValue": 0
        }, {
          "key": "in_2",
          "label": "Number Max",
          "description": "Number Max",
          "type": "integer",
          "defaultValue": 10
        }],
        "outputs": [{
          "key": "out_1",
          "label": "Number",
          "description": "Number",
          "type": "integer",
          "defaultValue": null
        }],
        "settings": []
      }];
      return producers;
    },

    getComputationals: function() {
      const computationals = [{
        "key": "ColleenClancy",
        "tag": "1.0",
        "name": "Colleen Clancy - dummy",
        "description": "Colleen Clancy - dummy",
        "inputs": [{
          "key": "in_1",
          "label": "File-url",
          "description": "File-url",
          "type": "file-url",
          "defaultValue": null
        }, {
          "key": "in_2",
          "label": "File-url",
          "description": "File-url",
          "type": "file-url",
          "defaultValue": null
        }, {
          "key": "in_3",
          "label": "NaValue",
          "description": "Na blocker drug concentration",
          "type": "integer",
          "defaultValue": 10
        }, {
          "key": "in_4",
          "label": "KrValue",
          "description": "Kr blocker drug concentration",
          "type": "integer",
          "defaultValue": 10
        }, {
          "key": "in_5",
          "label": "BCLValue",
          "description": "Basic cycle length (BCL)",
          "type": "integer",
          "defaultValue": 10
        }, {
          "key": "in_6",
          "label": "beatsValue",
          "description": "Number of beats",
          "type": "integer",
          "defaultValue": 10
        }, {
          "key": "in_7",
          "label": "LigandValue",
          "description": "Ligand concentration",
          "type": "integer",
          "defaultValue": 10
        }, {
          "key": "in_8",
          "label": "cAMKIIValue",
          "description": "Adjust cAMKII activity level",
          "type": "string",
          "widget": "selectBox",
          "cfg": {
            structure:
              ["A", "B", "C", "D"].map(
                k => ({
                  key: k.toLowerCase(),
                  label: k
                })
              )

          },
          "defaultValue": "c"
        }, {
          "key": "in_9",
          "label": "solverMode",
          "description": "Solver Mode",
          "type": "string",
          "widget": "selectBox",
          "cfg": {
            structure:
              ["0D", "1D", "2D"].map(
                k => ({
                  key: k.toLowerCase(),
                  label: k
                })
              )

          },
          "defaultValue": "0d"
        }],
        "outputs": [{
          "key": "out_1",
          "label": "csv-url",
          "description": "csv-url",
          "type": "csv-url",
          "defaultValue": null
        }],
        "settings": []
      }, {
        "key": "Computational2",
        "tag": "1.0",
        "name": "Computational 2",
        "description": "Computational 2",
        "inputs": [{
          "key": "in_1",
          "label": "Scene",
          "description": "Scene",
          "type": "scene",
          "defaultValue": null
        }],
        "outputs": [{
          "key": "out_1",
          "label": "Numbers",
          "description": "Other numbers",
          "type": "integer",
          "defaultValue": null
        }],
        "settings": []
      }, {
        "key": "masu.speag.com/simcore/services/comp/sleeper",
        "tag": "0.0.1",
        "name": "Sleeper",
        "description": "Sleeper",
        "inputs": [{
          "key": "in_1",
          "label": "File-url",
          "description": "File-url",
          "type": "file-url",
          "defaultValue": null
        }, {
          "key": "in_2",
          "label": "Number",
          "description": "Number",
          "type": "integer",
          "defaultValue": 0
        }, {
          "key": "in_3",
          "label": "Number",
          "description": "Sleep extra sec",
          "type": "integer",
          "defaultValue": 0
        }],
        "outputs": [{
          "key": "out_1",
          "label": "File-url",
          "description": "File-url",
          "type": "file-url",
          "defaultValue": null
        }, {
          "key": "out_2",
          "label": "Number",
          "description": "Number",
          "type": "integer",
          "defaultValue": 0
        }],
        "settings": []
      }];
      return computationals;
    },

    getAnalyses: function() {
      const analyses = [{
        "key": "jupyter-base-notebook",
        "tag": "1.0",
        "name": "Jupyter",
        "description": "Jupyter",
        "inputs": [{
          "key": "in_1",
          "label": "Number",
          "description": "Number",
          "type": "integer",
          "defaultValue": null
        }],
        "outputs": [],
        "settings": [],
        "viewer": {
          "ip": "http://" + window.location.hostname,
          "port": null
        }
      }, {
        "key": "Analysis2",
        "tag": "1.0",
        "name": "Analysis 2",
        "description": "Analysis 2",
        "inputs": [{
          "key": "in_1",
          "label": "Number",
          "description": "Number",
          "type": "integer",
          "defaultValue": null
        }],
        "outputs": [],
        "settings": []
      }, {
        "key": "csv-table-graph",
        "tag": "1.0",
        "name": "CSV Viewer",
        "description": "CSV Viewer",
        "inputs": [{
          "key": "in_1",
          "label": "csv-url",
          "description": "csv-url",
          "type": "file-url",
          "defaultValue": null
        }],
        "outputs": [],
        "settings": [],
        "viewer": {
          "ip": "http://" + window.location.hostname,
          "port": null
        }
      }];
      return analyses;
    }
  } // statics

});
