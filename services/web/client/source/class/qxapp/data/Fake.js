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
        name: "Template #1",
        description: "Sample used for the unidirectional pipelining",
        thumbnail: null,
        created: null,
        prjId: "00000000-0000-0000-0000-000000000001"
      });
      rawData.push(item1);

      let item2 = qx.data.marshal.Json.createModel({
        name: "Template #2",
        description: "Two not connected nodes",
        thumbnail: null,
        created: null,
        prjId: "00000000-0000-0000-0000-000000000002"
      });
      rawData.push(item2);

      // A wrapper around raw array to make it "bindable"
      var data = new qx.data.Array(rawData);
      return data;
    },

    getPrjData: function(prjId) {
      switch (prjId) {
        case "00000000-0000-0000-0000-000000000001":
          return this.getTemp1Data();
        case "00000000-0000-0000-0000-000000000002":
          return this.getTemp2Data();
      }
      return null;
    },

    getTemp1Data: function() {
      let temp1Data = {
        "nodes": [{
          "uuid": "dd329e10-a906-42da-a7b3-4c4fec4a786f",
          "key": "masu.speag.com/simcore/services/comp/sleeper",
          "tag": "1.0",
          "name": "Node 1",
          "desc": "Node 1",
          "position": {
            "x": 50,
            "y": 100
          },
          "inputs": [{
            "key": "in_1",
            "label": "File-url",
            "desc": "File-url",
            "type": "fileUrl",
            "value": null
          },
          {
            "key": "in_2",
            "label": "Number",
            "desc": "Number",
            "type": "integer",
            "value": null
          }],
          "outputs": [{
            "key": "out_1",
            "label": "File-url",
            "desc": "File-url",
            "type": "fileUrl",
            "value": null
          },
          {
            "key": "out_2",
            "label": "Number",
            "desc": "Number",
            "type": "integer",
            "value": null
          }],
          "settings": []
        }, {
          "uuid": "3fad99a2-31b3-48a2-9066-1a66fc21aa52",
          "key": "masu.speag.com/simcore/services/comp/sleeper",
          "tag": "1.0",
          "name": "Node 2",
          "desc": "Node 2",
          "position": {
            "x": 50,
            "y": 300
          },
          "inputs": [{
            "key": "in_1",
            "label": "File-url",
            "desc": "File-url",
            "type": "fileUrl",
            "value": null
          },
          {
            "key": "in_2",
            "label": "Number",
            "desc": "Number",
            "type": "integer",
            "value": null
          }],
          "outputs": [{
            "key": "out_1",
            "label": "File-url",
            "desc": "File-url",
            "type": "fileUrl",
            "value": null
          },
          {
            "key": "out_2",
            "label": "Number",
            "desc": "Number",
            "type": "integer",
            "value": null
          }],
          "settings": []
        }, {
          "uuid": "3a97f542-93c4-419c-b5c9-bcf9ff3ada7e",
          "key": "masu.speag.com/simcore/services/comp/sleeper",
          "tag": "1.0",
          "name": "Node 3",
          "desc": "Node 3",
          "position": {
            "x": 300,
            "y": 100
          },
          "inputs": [{
            "key": "in_1",
            "label": "File-url",
            "desc": "File-url",
            "type": "fileUrl",
            "value": null
          },
          {
            "key": "in_2",
            "label": "Number",
            "desc": "Number",
            "type": "integer",
            "value": null
          }],
          "outputs": [{
            "key": "out_1",
            "label": "File-url",
            "desc": "File-url",
            "type": "fileUrl",
            "value": null
          },
          {
            "key": "out_2",
            "label": "Number",
            "desc": "Number",
            "type": "integer",
            "value": null
          }],
          "settings": []
        }, {
          "uuid":"9c35ecbc-8219-4538-ba2e-bad8b6e64cda",
          "key": "masu.speag.com/simcore/services/comp/sleeper",
          "tag": "1.0",
          "name": "Node 4",
          "desc": "Node 4",
          "position": {
            "x": 300,
            "y": 300
          },
          "inputs": [{
            "key": "in_1",
            "label": "File-url",
            "desc": "File-url",
            "type": "fileUrl",
            "value": null
          },
          {
            "key": "in_2",
            "label": "Number",
            "desc": "Number",
            "type": "integer",
            "value": null
          }],
          "outputs": [{
            "key": "out_1",
            "label": "File-url",
            "desc": "File-url",
            "type": "fileUrl",
            "value": null
          },
          {
            "key": "out_2",
            "label": "Number",
            "desc": "Number",
            "type": "integer",
            "value": null
          }],
          "settings": []
        }, {
          "uuid":"51ad1bc0-615e-406a-9886-e3639f51208c",
          "key": "masu.speag.com/simcore/services/comp/sleeper",
          "tag": "1.0",
          "name": "Node 5",
          "desc": "Node 5",
          "position": {
            "x": 550,
            "y": 200
          },
          "inputs": [{
            "key": "in_1",
            "label": "File-url",
            "desc": "File-url",
            "type": "fileUrl",
            "value": null
          },
          {
            "key": "in_2",
            "label": "Number",
            "desc": "Number",
            "type": "integer",
            "value": null
          }],
          "outputs": [{
            "key": "out_1",
            "label": "File-url",
            "desc": "File-url",
            "type": "fileUrl",
            "value": null
          },
          {
            "key": "out_2",
            "label": "Number",
            "desc": "Number",
            "type": "integer",
            "value": null
          }],
          "settings": []
        }, {
          "uuid":"5df77702-29d5-4513-b3f8-f2a40ed317fe",
          "key": "masu.speag.com/simcore/services/comp/sleeper",
          "tag": "1.0",
          "name": "Node 6",
          "desc": "Node 6",
          "position": {
            "x": 800,
            "y": 100
          },
          "inputs": [{
            "key": "in_1",
            "label": "File-url",
            "desc": "File-url",
            "type": "fileUrl",
            "value": null
          },
          {
            "key": "in_2",
            "label": "Number",
            "desc": "Number",
            "type": "integer",
            "value": null
          }],
          "outputs": [{
            "key": "out_1",
            "label": "File-url",
            "desc": "File-url",
            "type": "fileUrl",
            "value": null
          },
          {
            "key": "out_2",
            "label": "Number",
            "desc": "Number",
            "type": "integer",
            "value": null
          }],
          "settings": []
        }, {
          "uuid": "de2c84ed-a3bc-47c2-b54d-84a5c048236b",
          "key": "masu.speag.com/simcore/services/comp/sleeper",
          "tag": "1.0",
          "name": "Node 7",
          "desc": "Node 7",
          "position": {
            "x": 800,
            "y": 300
          },
          "inputs": [{
            "key": "in_1",
            "label": "File-url",
            "desc": "File-url",
            "type": "fileUrl",
            "value": null
          },
          {
            "key": "in_2",
            "label": "Number",
            "desc": "Number",
            "type": "integer",
            "value": null
          }],
          "outputs": [{
            "key": "out_1",
            "label": "File-url",
            "desc": "File-url",
            "type": "fileUrl",
            "value": null
          },
          {
            "key": "out_2",
            "label": "Number",
            "desc": "Number",
            "type": "integer",
            "value": null
          }],
          "settings": []
        }, {
          "uuid": "ba22104c-99e1-45c9-a09d-228400a6f9fb",
          "key": "masu.speag.com/simcore/services/comp/sleeper",
          "tag": "1.0",
          "name": "Node 8",
          "desc": "Node 8",
          "position": {
            "x": 1050,
            "y": 200
          },
          "inputs": [{
            "key": "in_1",
            "label": "File-url",
            "desc": "File-url",
            "type": "fileUrl",
            "value": null
          },
          {
            "key": "in_2",
            "label": "Number",
            "desc": "Number",
            "type": "integer",
            "value": null
          }],
          "outputs": [{
            "key": "out_1",
            "label": "File-url",
            "desc": "File-url",
            "type": "fileUrl",
            "value": null
          },
          {
            "key": "out_2",
            "label": "Number",
            "desc": "Number",
            "type": "integer",
            "value": null
          }],
          "settings": []
        }],
        "links": [{
          "uuid": "348729ae-f24c-49dd-9382-29b8dc83c36f",
          "node1Id": "dd329e10-a906-42da-a7b3-4c4fec4a786f",
          "port1Id": "out_1",
          "node2Id": "3a97f542-93c4-419c-b5c9-bcf9ff3ada7e",
          "port2Id": "in_1"
        }, {
          "uuid": "348729ae-f24c-49dd-9382-29b8dc83c361",
          "node1Id": "dd329e10-a906-42da-a7b3-4c4fec4a786f",
          "port1Id": "out_2",
          "node2Id": "3a97f542-93c4-419c-b5c9-bcf9ff3ada7e",
          "port2Id": "in_2"
        }, {
          "uuid": "81b0fd72-ff2b-451f-9d3e-2d2e99967302",
          "node1Id": "3fad99a2-31b3-48a2-9066-1a66fc21aa52",
          "port1Id": "out_1",
          "node2Id": "9c35ecbc-8219-4538-ba2e-bad8b6e64cda",
          "port2Id": "in_1"
        }, {
          "uuid": "81b0fd72-ff2b-451f-9d3e-2d2e99967301",
          "node1Id": "3fad99a2-31b3-48a2-9066-1a66fc21aa52",
          "port1Id": "out_2",
          "node2Id": "9c35ecbc-8219-4538-ba2e-bad8b6e64cda",
          "port2Id": "in_2"
        }, {
          "uuid": "f458bdd2-34b0-4989-a8fb-e6aad9362e10",
          "node1Id": "3a97f542-93c4-419c-b5c9-bcf9ff3ada7e",
          "port1Id": "out_1",
          "node2Id": "51ad1bc0-615e-406a-9886-e3639f51208c",
          "port2Id": "in_1"
        }, {
          "uuid": "95728bbf-a910-4136-a1e0-756bb786c14e",
          "node1Id": "9c35ecbc-8219-4538-ba2e-bad8b6e64cda",
          "port1Id": "out_2",
          "node2Id": "51ad1bc0-615e-406a-9886-e3639f51208c",
          "port2Id": "in_2"
        }, {
          "uuid": "3d280cee-9a90-4333-96ae-d6ee2526223c",
          "node1Id": "51ad1bc0-615e-406a-9886-e3639f51208c",
          "port1Id": "out_1",
          "node2Id": "5df77702-29d5-4513-b3f8-f2a40ed317fe",
          "port2Id": "in_1"
        }, {
          "uuid": "fc5eae4c-5632-4aba-8047-40ab47ae8f58",
          "node1Id": "51ad1bc0-615e-406a-9886-e3639f51208c",
          "port1Id": "out_2",
          "node2Id": "de2c84ed-a3bc-47c2-b54d-84a5c048236b",
          "port2Id": "in_2"
        }, {
          "uuid": "b2e7ec46-eac5-44a1-90b8-0e571b5bf695",
          "node1Id": "5df77702-29d5-4513-b3f8-f2a40ed317fe",
          "port1Id": "out_1",
          "node2Id": "ba22104c-99e1-45c9-a09d-228400a6f9fb",
          "port2Id": "in_1"
        }, {
          "uuid": "653c5a2a-81a2-4266-a06d-34624a760e67",
          "node1Id": "de2c84ed-a3bc-47c2-b54d-84a5c048236b",
          "port1Id": "out_2",
          "node2Id": "ba22104c-99e1-45c9-a09d-228400a6f9fb",
          "port2Id": "in_2"
        }]
      };
      return temp1Data;
    },

    getTemp2Data: function() {
      let temp2Data = {
        "nodes": [{
          "uuid": "cd90ad2c-8dac-49b5-8552-dd9fbf785273",
          "key": "node1",
          "tag": "1.0",
          "name": "Node 1",
          "desc": "Node 1",
          "position": {
            "x": 50,
            "y": 100
          },
          "inputs": [],
          "outputs": [{
            "key": "out_1",
            "label": "Number",
            "desc": "Number",
            "type": "integer",
            "value": ""
          }, {
            "key": "out_2",
            "label": "String",
            "desc": "String",
            "type": "string",
            "value": ""
          }, {
            "key": "out_3",
            "label": "Bool",
            "desc": "Bool",
            "type": "bool",
            "value": null
          }],
          "settings": []
        }, {
          "uuid": "ad45ba4e-2dac-43bb-afad-86c9d50a2ec9",
          "key": "node2",
          "tag": "1.0",
          "name": "Node 2",
          "desc": "Node 2",
          "position": {
            "x": 400,
            "y": 100
          },
          "inputs": [{
            "key": "in_1",
            "label": "Number",
            "desc": "Number",
            "type": "integer",
            "value": null
          }, {
            "key": "in_2",
            "label": "String",
            "desc": "String",
            "type": "string",
            "value": null
          }, {
            "key": "in_3",
            "label": "Bool",
            "desc": "Bool",
            "type": "bool",
            "value": null
          }],
          "outputs": [],
          "settings": [{
            "key": "sett_1",
            "label": "Bool_1",
            "desc": "Bool_1",
            "type": "bool",
            "value": 0
          }, {
            "key": "sett_2",
            "label": "Bool_2",
            "desc": "Bool_2",
            "type": "bool",
            "value": 0
          }]
        }, {
          "uuid": "13e1915f-b463-47c5-bb94-fe25effe30da",
          "key": "node3",
          "tag": "1.0",
          "name": "Node 3",
          "desc": "Node 3",
          "position": {
            "x": 400,
            "y": 300
          },
          "inputs": [{
            "key": "in_1",
            "label": "String",
            "desc": "String",
            "type": "string",
            "value": null
          }, {
            "key": "in_2",
            "label": "Number",
            "desc": "Number",
            "type": "integer",
            "value": null
          }],
          "outputs": [],
          "settings": []
        }],
        "links": []
      };
      return temp2Data;
    },

    getServices: function() {
      let availableServices = [];
      Array.prototype.push.apply(availableServices, qxapp.data.Fake.getProducers());
      Array.prototype.push.apply(availableServices, qxapp.data.Fake.getComputationals());
      Array.prototype.push.apply(availableServices, qxapp.data.Fake.getAnalyses());
      return availableServices;
    },

    getProducers: function() {
      const producers = [{
        "key": "modeler",
        "tag": "1.0",
        "name": "Modeler",
        "desc": "Modeler",
        "inputs": [{
          "key": "in_1",
          "label": "ViPModel",
          "desc": "Select ViP Model",
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
          "desc": "Scene",
          "type": "scene",
          "defaultValue": null
        }],
        "settings": [],
        "viewer": {
          "ip": "http://" + window.location.hostname,
          "port": null
        }
      }, {
        "key": "FileManager",
        "tag": "1.0",
        "name": "File Manager",
        "desc": "File Manager",
        "inputs": [],
        "outputs": [{
          "key": "out_1",
          "label": "File-url",
          "desc": "File-url",
          "type": "fileUrl",
          "defaultValue": null
        }],
        "settings": []
      }, {
        "key": "RandomNumberGeneratorID",
        "tag": "1.0",
        "name": "Random Number Generator",
        "desc": "Random Number Generator",
        "inputs": [{
          "key": "in_1",
          "label": "Number Min",
          "desc": "Number Min",
          "type": "integer",
          "defaultValue": 0
        }, {
          "key": "in_2",
          "label": "Number Max",
          "desc": "Number Max",
          "type": "integer",
          "defaultValue": 10
        }],
        "outputs": [{
          "key": "out_1",
          "label": "Number",
          "desc": "Number",
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
        "desc": "Colleen Clancy - dummy",
        "inputs": [{
          "key": "in_1",
          "label": "File-url",
          "desc": "File-url",
          "type": "fileUrl",
          "defaultValue": null
        }, {
          "key": "in_2",
          "label": "File-url",
          "desc": "File-url",
          "type": "fileUrl",
          "defaultValue": null
        }, {
          "key": "in_3",
          "label": "NaValue",
          "desc": "Na blocker drug concentration",
          "type": "integer",
          "defaultValue": 10
        }, {
          "key": "in_4",
          "label": "KrValue",
          "desc": "Kr blocker drug concentration",
          "type": "integer",
          "defaultValue": 10
        }, {
          "key": "in_5",
          "label": "BCLValue",
          "desc": "Basic cycle length (BCL)",
          "type": "integer",
          "defaultValue": 10
        }, {
          "key": "in_6",
          "label": "beatsValue",
          "desc": "Number of beats",
          "type": "integer",
          "defaultValue": 10
        }, {
          "key": "in_7",
          "label": "LigandValue",
          "desc": "Ligand concentration",
          "type": "integer",
          "defaultValue": 10
        }, {
          "key": "in_8",
          "label": "cAMKIIValue",
          "desc": "Adjust cAMKII activity level",
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
          "desc": "Solver Mode",
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
          "desc": "csv-url",
          "type": "csv-url",
          "defaultValue": null
        }],
        "settings": []
      }, {
        "key": "Computational2",
        "tag": "1.0",
        "name": "Computational 2",
        "desc": "Computational 2",
        "inputs": [{
          "key": "in_1",
          "label": "Scene",
          "desc": "Scene",
          "type": "scene",
          "defaultValue": null
        }],
        "outputs": [{
          "key": "out_1",
          "label": "Numbers",
          "desc": "Other numbers",
          "type": "integer",
          "defaultValue": null
        }],
        "settings": []
      }, {
        "key": "masu.speag.com/simcore/services/comp/sleeper",
        "tag": "1.0",
        "name": "Sleeper",
        "desc": "Sleeper",
        "inputs": [{
          "key": "in_1",
          "label": "File-url",
          "desc": "File-url",
          "type": "fileUrl",
          "defaultValue": null
        }, {
          "key": "in_2",
          "label": "Number",
          "desc": "Number",
          "type": "integer",
          "defaultValue": 0
        }, {
          "key": "in_3",
          "label": "Number",
          "desc": "Sleep extra sec",
          "type": "integer",
          "defaultValue": 0
        }],
        "outputs": [{
          "key": "out_1",
          "label": "File-url",
          "desc": "File-url",
          "type": "fileUrl",
          "defaultValue": null
        }, {
          "key": "out_2",
          "label": "Number",
          "desc": "Number",
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
        "desc": "Jupyter",
        "inputs": [{
          "key": "in_1",
          "label": "Number",
          "desc": "Number",
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
        "desc": "Analysis 2",
        "inputs": [{
          "key": "in_1",
          "label": "Number",
          "desc": "Number",
          "type": "integer",
          "defaultValue": null
        }],
        "outputs": [],
        "settings": []
      }, {
        "key": "csv-table-graph",
        "tag": "1.0",
        "name": "CSV Viewer",
        "desc": "CSV Viewer",
        "inputs": [{
          "key": "in_1",
          "label": "csv-url",
          "desc": "csv-url",
          "type": "csv-url",
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
