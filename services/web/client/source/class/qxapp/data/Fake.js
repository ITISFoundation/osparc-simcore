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

      var item = qx.data.marshal.Json.createModel({
        name: "Template #1",
        description: "Sample used for the unidirectional pipelining",
        thumbnail: null,
        created: null,
        prjId: "00000000-0000-0000-0000-000000000001"
      });
      rawData.push(item);

      // A wrapper around raw array to make it "bindable"
      var data = new qx.data.Array(rawData);
      return data;
    },

    getPrjData: function(prjId) {
      if (prjId === "00000000-0000-0000-0000-000000000001") {
        return this.getTemp1Data();
      }
      return null;
    },

    getTemp1Data: function() {
      let temp1Data = [{
        "uuid": "dd329e10-a906-42da-a7b3-4c4fec4a786f",
        "id": "sleeper",
        "name": "Node 1",
        "position": {
          "x": 50,
          "y": 100
        },
        "input": [],
        "output": [{
          "name": "Number",
          "type": "number",
          "value": ""
        }],
        "settings": [],
        "children": ["3a97f542-93c4-419c-b5c9-bcf9ff3ada7e"]
      }, {
        "uuid": "3fad99a2-31b3-48a2-9066-1a66fc21aa52",
        "id": "sleeper",
        "name": "Node 2",
        "position": {
          "x": 50,
          "y": 300
        },
        "input": [],
        "output": [{
          "name": "Number",
          "type": "number",
          "value": ""
        }],
        "settings": [],
        "children": ["9c35ecbc-8219-4538-ba2e-bad8b6e64cda"]
      }, {
        "uuid": "3a97f542-93c4-419c-b5c9-bcf9ff3ada7e",
        "id": "sleeper",
        "name": "Node 3",
        "position": {
          "x": 300,
          "y": 100
        },
        "input": [{
          "name": "Number",
          "type": "number",
          "value": ""
        }],
        "output": [{
          "name": "Number",
          "type": "number",
          "value": ""
        }],
        "settings": [],
        "children": ["51ad1bc0-615e-406a-9886-e3639f51208c"]
      }, {
        "uuid":"9c35ecbc-8219-4538-ba2e-bad8b6e64cda",
        "id": "sleeper",
        "name": "Node 4",
        "position": {
          "x": 300,
          "y": 300
        },
        "input": [{
          "name": "Number",
          "type": "number",
          "value": ""
        }],
        "output": [{
          "name": "Number",
          "type": "number",
          "value": ""
        }],
        "settings": [],
        "children": ["51ad1bc0-615e-406a-9886-e3639f51208c"]
      }, {
        "uuid":"51ad1bc0-615e-406a-9886-e3639f51208c",
        "id": "sleeper",
        "name": "Node 5",
        "position": {
          "x": 550,
          "y": 200
        },
        "input": [{
          "name": "Number",
          "type": "number",
          "value": ""
        }],
        "output": [{
          "name": "Number",
          "type": "number",
          "value": ""
        }],
        "settings": [],
        "children": ["5df77702-29d5-4513-b3f8-f2a40ed317fe", "de2c84ed-a3bc-47c2-b54d-84a5c048236b"]
      }, {
        "uuid":"5df77702-29d5-4513-b3f8-f2a40ed317fe",
        "id": "sleeper",
        "name": "Node 6",
        "position": {
          "x": 800,
          "y": 100
        },
        "input": [{
          "name": "Number",
          "type": "number",
          "value": ""
        }],
        "output": [{
          "name": "Number",
          "type": "number",
          "value": ""
        }],
        "settings": [],
        "children": ["ba22104c-99e1-45c9-a09d-228400a6f9fb"]
      }, {
        "uuid": "de2c84ed-a3bc-47c2-b54d-84a5c048236b",
        "id": "sleeper",
        "name": "Node 7",
        "position": {
          "x": 800,
          "y": 300
        },
        "input": [{
          "name": "Number",
          "type": "number",
          "value": ""
        }],
        "output": [{
          "name": "Number",
          "type": "number",
          "value": ""
        }],
        "settings": [],
        "children": ["ba22104c-99e1-45c9-a09d-228400a6f9fb"]
      }, {
        "uuid": "ba22104c-99e1-45c9-a09d-228400a6f9fb",
        "position": {
          "x": 1050,
          "y": 200
        },
        "id": "sleeper",
        "name": "Node 8",
        "input": [{
          "name": "Number",
          "type": "number",
          "value": ""
        }],
        "output": [],
        "settings": [],
        "children": []
      }];
      return temp1Data;
    },

    getProducers: function() {
      const producers = [{
        "id": "modeler",
        "name": "Modeler",
        "input": [],
        "output": [{
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
      },
      {
        "id": "NumberGeneratorID",
        "name": "Number Generator",
        "input": [],
        "output": [{
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
        "input": [],
        "output": [
          {
            "name": "outputFolder",
            "type": "folder",
            "value": "url"
          },
          {
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
          }
        ],
        "settings": [
          {
            "name": "NaValue",
            "text": "Na blocker drug concentration",
            "type": "number",
            "exposed": false,
            "value": 10
          },
          {
            "name": "KrValue",
            "text": "Kr blocker drug concentration",
            "type": "number",
            "exposed": false,
            "value": 10
          },
          {
            "name": "BCLValue",
            "text": "Basic cycle length (BCL)",
            "type": "number",
            "exposed": false,
            "value": 10
          },
          {
            "name": "beatsValue",
            "text": "Number of beats",
            "type": "number",
            "exposed": false,
            "value": 10
          },
          {
            "name": "LigandValue",
            "text": "Ligand concentration",
            "type": "number",
            "exposed": false,
            "value": 10
          },
          {
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
          }
        ]
      },
      {
        "id": "Computational2",
        "name": "Computational 2",
        "input": [{
          "name": "Scene",
          "type": "scene",
          "value": ""
        }],
        "output": [{
          "name": "Other numbers",
          "type": "number",
          "value": ""
        }],
        "settings": []
      },
      {
        "id": "Computational3",
        "name": "Computational 3",
        "input": [{
          "name": "Number",
          "type": "number",
          "value": ""
        }],
        "output": [{
          "name": "Some numbers",
          "type": "number",
          "value": ""
        }],
        "settings": []
      },
      {
        "id": "Computational4",
        "name": "Computational 4",
        "input": [{
          "name": "Number",
          "type": "number",
          "value": ""
        }],
        "output": [{
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
        "input": [{
          "name": "Number",
          "type": "number",
          "value": ""
        }],
        "output": [],
        "settings": [],
        "viewer": {
          "ip": "http://" + window.location.hostname,
          "port": null
        }
      },
      {
        "id": "Analysis2",
        "name": "Analysis 2",
        "input": [{
          "name": "Number",
          "type": "scene",
          "value": ""
        }],
        "output": [],
        "settings": []
      }];
      return analyses;
    }
  } // statics

});
