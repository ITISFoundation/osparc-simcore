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
          "id": "sleeper",
          "name": "Node 1",
          "position": {
            "x": 50,
            "y": 100
          },
          "inputs": [],
          "outputs": [{
            "uuid": "b17e3436-a214-4280-b40f-01cddd8237bb",
            "name": "Number",
            "type": "number",
            "value": ""
          }],
          "settings": []
        }, {
          "uuid": "3fad99a2-31b3-48a2-9066-1a66fc21aa52",
          "id": "sleeper",
          "name": "Node 2",
          "position": {
            "x": 50,
            "y": 300
          },
          "inputs": [],
          "outputs": [{
            "uuid": "3e25e028-a1f1-42ec-967a-3416417913e2",
            "name": "Number",
            "type": "number",
            "value": ""
          }],
          "settings": []
        }, {
          "uuid": "3a97f542-93c4-419c-b5c9-bcf9ff3ada7e",
          "id": "sleeper",
          "name": "Node 3",
          "position": {
            "x": 300,
            "y": 100
          },
          "inputs": [{
            "uuid": "ccea40bd-53ee-453a-8154-32ee7e5a80b8",
            "name": "Number",
            "type": "number",
            "value": ""
          }],
          "outputs": [{
            "uuid": "fff13fb5-35fd-4d1b-92a3-e3fb57b5a948",
            "name": "Number",
            "type": "number",
            "value": ""
          }],
          "settings": []
        }, {
          "uuid":"9c35ecbc-8219-4538-ba2e-bad8b6e64cda",
          "id": "sleeper",
          "name": "Node 4",
          "position": {
            "x": 300,
            "y": 300
          },
          "inputs": [{
            "uuid": "8f296d86-bf95-4ad0-8a74-4b0a932d9f37",
            "name": "Number",
            "type": "number",
            "value": ""
          }],
          "outputs": [{
            "uuid": "62a8c0f7-e2b2-4c94-89a9-34a89d0d7cd2",
            "name": "Number",
            "type": "number",
            "value": ""
          }],
          "settings": []
        }, {
          "uuid":"51ad1bc0-615e-406a-9886-e3639f51208c",
          "id": "sleeper",
          "name": "Node 5",
          "position": {
            "x": 550,
            "y": 200
          },
          "inputs": [{
            "uuid": "c28f007c-b8e8-44b2-9400-52b0715a04e4",
            "name": "Number",
            "type": "number",
            "value": ""
          }],
          "outputs": [{
            "uuid": "99a3e2c7-197b-4169-803f-000c4a403232",
            "name": "Number",
            "type": "number",
            "value": ""
          }],
          "settings": []
        }, {
          "uuid":"5df77702-29d5-4513-b3f8-f2a40ed317fe",
          "id": "sleeper",
          "name": "Node 6",
          "position": {
            "x": 800,
            "y": 100
          },
          "inputs": [{
            "uuid": "acdda27c-12bc-4af3-9eda-1a3a29f36768",
            "name": "Number",
            "type": "number",
            "value": ""
          }],
          "outputs": [{
            "uuid": "30974de2-6fe3-4c70-be7c-0b472c7596fa",
            "name": "Number",
            "type": "number",
            "value": ""
          }],
          "settings": []
        }, {
          "uuid": "de2c84ed-a3bc-47c2-b54d-84a5c048236b",
          "id": "sleeper",
          "name": "Node 7",
          "position": {
            "x": 800,
            "y": 300
          },
          "inputs": [{
            "uuid": "92d41a2f-7e0f-48f5-839e-b94905d3f8a1",
            "name": "Number",
            "type": "number",
            "value": ""
          }],
          "outputs": [{
            "uuid": "50a54668-4f9d-495a-82c4-a1521acb188c",
            "name": "Number",
            "type": "number",
            "value": ""
          }],
          "settings": []
        }, {
          "uuid": "ba22104c-99e1-45c9-a09d-228400a6f9fb",
          "position": {
            "x": 1050,
            "y": 200
          },
          "id": "sleeper",
          "name": "Node 8",
          "inputs": [{
            "uuid": "bce542bc-7787-4c2c-b7a7-fe13c692c0a5",
            "name": "Number",
            "type": "number",
            "value": ""
          }],
          "outputs": [],
          "settings": []
        }],
        "links": [{
          "linkId": "348729ae-f24c-49dd-9382-29b8dc83c36f",
          "node1Id": "dd329e10-a906-42da-a7b3-4c4fec4a786f",
          "port1Id": "b17e3436-a214-4280-b40f-01cddd8237bb",
          "node2Id": "3a97f542-93c4-419c-b5c9-bcf9ff3ada7e",
          "port2Id": "ccea40bd-53ee-453a-8154-32ee7e5a80b8"
        }, {
          "linkId": "81b0fd72-ff2b-451f-9d3e-2d2e99967302",
          "node1Id": "3fad99a2-31b3-48a2-9066-1a66fc21aa52",
          "port1Id": "3e25e028-a1f1-42ec-967a-3416417913e2",
          "node2Id": "9c35ecbc-8219-4538-ba2e-bad8b6e64cda",
          "port2Id": "8f296d86-bf95-4ad0-8a74-4b0a932d9f37"
        }, {
          "linkId": "f458bdd2-34b0-4989-a8fb-e6aad9362e10",
          "node1Id": "3a97f542-93c4-419c-b5c9-bcf9ff3ada7e",
          "port1Id": "fff13fb5-35fd-4d1b-92a3-e3fb57b5a948",
          "node2Id": "51ad1bc0-615e-406a-9886-e3639f51208c",
          "port2Id": "c28f007c-b8e8-44b2-9400-52b0715a04e4"
        }, {
          "linkId": "95728bbf-a910-4136-a1e0-756bb786c14e",
          "node1Id": "9c35ecbc-8219-4538-ba2e-bad8b6e64cda",
          "port1Id": "62a8c0f7-e2b2-4c94-89a9-34a89d0d7cd2",
          "node2Id": "51ad1bc0-615e-406a-9886-e3639f51208c",
          "port2Id": "c28f007c-b8e8-44b2-9400-52b0715a04e4"
        }, {
          "linkId": "3d280cee-9a90-4333-96ae-d6ee2526223c",
          "node1Id": "51ad1bc0-615e-406a-9886-e3639f51208c",
          "port1Id": "99a3e2c7-197b-4169-803f-000c4a403232",
          "node2Id": "5df77702-29d5-4513-b3f8-f2a40ed317fe",
          "port2Id": "acdda27c-12bc-4af3-9eda-1a3a29f36768"
        }, {
          "linkId": "fc5eae4c-5632-4aba-8047-40ab47ae8f58",
          "node1Id": "51ad1bc0-615e-406a-9886-e3639f51208c",
          "port1Id": "99a3e2c7-197b-4169-803f-000c4a403232",
          "node2Id": "de2c84ed-a3bc-47c2-b54d-84a5c048236b",
          "port2Id": "92d41a2f-7e0f-48f5-839e-b94905d3f8a1"
        }, {
          "linkId": "b2e7ec46-eac5-44a1-90b8-0e571b5bf695",
          "node1Id": "5df77702-29d5-4513-b3f8-f2a40ed317fe",
          "port1Id": "30974de2-6fe3-4c70-be7c-0b472c7596fa",
          "node2Id": "ba22104c-99e1-45c9-a09d-228400a6f9fb",
          "port2Id": "bce542bc-7787-4c2c-b7a7-fe13c692c0a5"
        }, {
          "linkId": "653c5a2a-81a2-4266-a06d-34624a760e67",
          "node1Id": "de2c84ed-a3bc-47c2-b54d-84a5c048236b",
          "port1Id": "50a54668-4f9d-495a-82c4-a1521acb188c",
          "node2Id": "ba22104c-99e1-45c9-a09d-228400a6f9fb",
          "port2Id": "bce542bc-7787-4c2c-b7a7-fe13c692c0a5"
        }]
      };
      return temp1Data;
    },

    getTemp2Data: function() {
      let temp2Data = {
        "nodes": [{
          "uuid": "cd90ad2c-8dac-49b5-8552-dd9fbf785273",
          "id": "sleeper",
          "name": "Node 1",
          "position": {
            "x": 50,
            "y": 100
          },
          "inputs": [],
          "outputs": [{
            "uuid": "7d4a5879-443d-4387-99f9-31da91e38f2e",
            "name": "Number",
            "type": "number",
            "value": ""
          }, {
            "uuid": "53bdb908-1b00-42d9-9c37-473a9fff4f79",
            "name": "String",
            "type": "string",
            "value": ""
          }],
          "settings": []
        }, {
          "uuid": "ad45ba4e-2dac-43bb-afad-86c9d50a2ec9",
          "id": "sleeper",
          "name": "Node 2",
          "position": {
            "x": 400,
            "y": 100
          },
          "inputs": [{
            "uuid": "3fe506fc-8c43-46af-bb65-2c4fea471059",
            "name": "Number",
            "type": "number",
            "value": ""
          }, {
            "uuid": "4bf3665e-0dfe-4c58-8d43-278768b396be",
            "name": "String",
            "type": "string",
            "value": ""
          }, {
            "uuid": "4bf3665e-0dfe-4c58-8d43-278768b39634",
            "name": "Bool",
            "type": "bool",
            "value": ""
          }, {
            "uuid": "4bf3665e-0dfe-4c58-8d43-278768b39635",
            "name": "Bool",
            "type": "bool",
            "value": ""
          }, {
            "uuid": "4bf3665e-0dfe-4c58-8d43-278768b39636",
            "name": "Bool",
            "type": "bool",
            "value": ""
          }],
          "outputs": [],
          "settings": []
        }, {
          "uuid": "13e1915f-b463-47c5-bb94-fe25effe30da",
          "id": "sleeper",
          "name": "Node 3",
          "position": {
            "x": 400,
            "y": 300
          },
          "inputs": [{
            "uuid": "2fd31c28-ee78-4dd1-9736-97ee83c19da3",
            "name": "String",
            "type": "string",
            "value": ""
          }, {
            "uuid": "0dc9edf6-e48a-4696-8aaa-86b7b700d925",
            "name": "Number",
            "type": "number",
            "value": ""
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
        "id": "modeler",
        "name": "Modeler",
        "inputs": [],
        "outputs": [{
          "name": "Scene",
          "type": "scene",
          "value": ""
        }],
        "settings": [{
          "name": "ViPModel",
          "options": [
            "Rat",
            "Sphere"
          ],
          "text": "Select ViP Model",
          "type": "select",
          "value": 0
        }],
        "viewer": {
          "ip": "http://" + window.location.hostname,
          "port": null
        }
      }, {
        "id": "FileReader",
        "name": "File Reader",
        "inputs": [],
        "outputs": [{
          "name": "File-url",
          "type": "file-url",
          "value": ""
        }],
        "settings": [{
          "name": "file",
          "text": "File",
          "type": "file",
          "value": ""
        }, {
          "name": "text",
          "text": "File type",
          "type": "text",
          "value": ""
        }]
      }, {
        "id": "NumberGeneratorID",
        "name": "Number Generator",
        "inputs": [],
        "outputs": [{
          "name": "Number",
          "type": "number",
          "value": ""
        }],
        "settings": [{
          "name": "number",
          "text": "Number",
          "type": "number",
          "value": 0
        }]
      }];
      return producers;
    },

    getComputationals: function() {
      const computationals = [{
        "id": "ColleenClancy",
        "name": "Colleen Clancy - dummy",
        "inputs": [{
          "name": "File-url",
          "type": "file-url",
          "value": ""
        }, {
          "name": "File-url",
          "type": "file-url",
          "value": ""
        }],
        "outputs": [{
          "name": "outputFolder",
          "type": "folder",
          "value": "url"
        }, {
          "name": "Allresults",
          "order": [
            "t",
            "I_Ca_store",
            "Ito",
            "Itof",
            "Itos",
            "INa",
            "IK1",
            "s1",
            "k1",
            "Jserca",
            "Iks",
            "Jleak",
            "ICFTR",
            "Incx"
          ],
          "type": "csv"
        }],
        "settings": [{
          "name": "NaValue",
          "text": "Na blocker drug concentration",
          "type": "number",
          "exposed": false,
          "value": 10
        }, {
          "name": "KrValue",
          "text": "Kr blocker drug concentration",
          "type": "number",
          "exposed": false,
          "value": 10
        }, {
          "name": "BCLValue",
          "text": "Basic cycle length (BCL)",
          "type": "number",
          "exposed": false,
          "value": 10
        }, {
          "name": "beatsValue",
          "text": "Number of beats",
          "type": "number",
          "exposed": false,
          "value": 10
        }, {
          "name": "LigandValue",
          "text": "Ligand concentration",
          "type": "number",
          "exposed": false,
          "value": 10
        }, {
          "name": "cAMKIIValue",
          "options": [
            "A",
            "B",
            "C",
            "D"
          ],
          "text": "Adjust cAMKII activity level",
          "type": "select",
          "exposed": false,
          "value": 0
        }]
      }, {
        "id": "Computational2",
        "name": "Computational 2",
        "inputs": [{
          "name": "Scene",
          "type": "scene",
          "value": ""
        }],
        "outputs": [{
          "name": "Other numbers",
          "type": "number",
          "value": ""
        }],
        "settings": []
      }, {
        "id": "Computational3",
        "name": "Computational 3",
        "inputs": [{
          "name": "Number",
          "type": "number",
          "value": ""
        }],
        "outputs": [{
          "name": "Some numbers",
          "type": "number",
          "value": ""
        }],
        "settings": []
      }, {
        "id": "Computational4",
        "name": "Computational 4",
        "inputs": [{
          "name": "Number",
          "type": "number",
          "value": ""
        }],
        "outputs": [{
          "name": "Other numbers",
          "type": "number",
          "value": ""
        }],
        "settings": []
      }];
      return computationals;
    },

    getAnalyses: function() {
      const analyses = [{
        "id": "jupyter-base-notebook",
        "name": "Jupyter",
        "inputs": [{
          "name": "Number",
          "type": "number",
          "value": ""
        }],
        "outputs": [],
        "settings": [],
        "viewer": {
          "ip": "http://" + window.location.hostname,
          "port": null
        }
      }, {
        "id": "Analysis2",
        "name": "Analysis 2",
        "inputs": [{
          "name": "Number",
          "type": "number",
          "value": ""
        }],
        "outputs": [],
        "settings": []
      }];
      return analyses;
    }
  } // statics

});
