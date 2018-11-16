/**
 *  Collection of free function with fake data for testing
 *
 * TODO: Use faker https://scotch.io/tutorials/generate-fake-data-for-your-javascript-applications-using-faker
 */

/* global window */

qx.Class.define("qxapp.dev.fake.Data", {
  type: "static",

  statics: {
    getNodeMap: function() {
      return {
        "services/computational/itis/sleeper-0.0.0":{
          key: "services/computational/itis/sleeper",
          version: "0.0.0",
          type: "computational",
          name: "sleeper service",
          description: "dummy sleepr service",
          authors: [
            {
              name: "Odei Maiz",
              email: "maiz@itis.ethz.ch"
            }
          ],
          contact: "maiz@itis.ethz.ch",
          inputs: {
            inNumber: {
              displayOrder: 0,
              label: "In",
              description: "Chosen Number",
              type: "number",
              defaultValue: 42
            }
          },
          outputs: {
            outNumber: {
              displayOrder: 0,
              label: "Out",
              description: "Chosen Number",
              type: "number"
            }
          }
        },
        "services/computational/itis/tutti-0.0.0-alpha": {
          key: "services/computational/itis/tutti",
          version: "0.0.0-alpha",
          type: "computational",
          name: "a little test node",
          description: "just the bare minimum",
          authors: [
            {
              name: "Tobias Oetiker",
              email: "oetiker@itis.ethz.ch"
            }
          ],
          contact: "oetiker@itis.ethz.ch",
          inputs: {
            inNumber: {
              displayOrder: 0,
              label: "Number Test",
              description: "Test Input for Number",
              type: "number",
              defaultValue: 5.3
            },
            inInt: {
              displayOrder: 1,
              label: "Integer Test",
              description: "Test Input for Integer",
              type: "integer",
              defaultValue: 2
            },
            inBool: {
              displayOrder: 2,
              label: "Boolean Test",
              type: "boolean",
              description: "Test Input for Boolean",
              defaultValue: true
            },
            inStr: {
              displayOrder: 3,
              type: "string",
              label: "String Test",
              description: "Test Input for String",
              defaultValue: "Gugus"
            },
            inArea: {
              displayOrder: 4,
              type: "string",
              label: "Widget TextArea Test",
              description: "Test Input for String",
              defaultValue: "Gugus\nDu\nDa",
              widget: {
                type: "TextArea",
                minHeight: 50
              }
            },
            inSb: {
              displayOrder: 5,
              label: "Widget SelectBox Test",
              description: "Test Input for SelectBox",
              defaultValue: "dog",
              type: "string",
              widget: {
                /*
                type: "SelectBox",
                structure: [
                  {
                    key: "dog",
                    label: "A Dog"
                  },
                  {
                    key: "cat",
                    label: "A Cat"
                  }
                ]
                */
                type: "TextArea",
                minHeight: 50
              }
            },
            inFile: {
              displayOrder: 6,
              label: "File",
              description: "Test Input File",
              type: "data:*/*"
            },
            inImage: {
              displayOrder: 7,
              label: "Image",
              description: "Test Input Image",
              type: "data:[image/jpeg,image/png]"
            }
          },
          outputs: {
            outNumber: {
              label: "Number Test",
              description: "Test Output for Number",
              displayOrder: 0,
              type: "number"
            },
            outInteger: {
              label: "Integer Test",
              description: "Test Output for Integer",
              displayOrder: 1,
              type: "integer"
            },
            outBool: {
              label: "Boolean Test",
              description: "Test Output for Boolean",
              displayOrder: 2,
              type: "boolean"
            },
            outPng: {
              label: "Png Test",
              description: "Test Output for PNG Image",
              displayOrder: 3,
              type: "data:image/png"
            }
          }
        }
      };
    },

    getUserProjectList: function() {
      return [
        {
          projectUuid: "07640335-a91f-468c-ab69-a374fa82078d",
          name: "Sample Project",
          description: "A little fake project without actual backend",
          notes: "# title\nThere be dragons inside",
          owner: "TOBI",
          collaborators: {
            "PEDRO": [
              "read",
              "write"
            ]
          },
          creationDate: "2018-07-02T16:01:00Z",
          lastChangeDate: "2018-07-02T16:02:22Z",
          thumbnail: "https://placeimg.com/171/96/tech/grayscale/?0.jpg",
          workbench: {
            "UUID1": {
              key: "services/dynamic/itis/file-picker",
              version: "0.0.0",
              outputs: {
                outFile: {
                  store: "s3-z43",
                  path: "/bucket1/file1"
                }
              },
              position: {
                x: 10,
                y: 10
              }
            },
            "UUID2": {
              key: "services/computational/itis/sleeper",
              version: "0.0.0",
              label: "Sleeper 1",
              inputs: {
                inNumber: 3.5
              },
              outputs: {
                outNumber: 33
              },
              position: {
                x: 400,
                y: 10
              }
            },
            "UUID3": {
              key: "services/computational/itis/sleeper",
              version: "0.0.0",
              label: "Sleeper 2",
              inputs: {
                inNumber: 3.5
              },
              outputs: {
                outNumber: 32
              },
              position: {
                x: 10,
                y: 300
              }
            },
            "UUID4": {
              key: "services/computational/itis/tutti",
              version: "0.0.0-alpha",
              inputs: {
                inNumber: {
                  nodeUuid: "UUID3",
                  output: "outNumber"
                },
                inInt: 372,
                inBool: true,
                inStr: "Ooops, Agnodain",
                inArea: "some\nmore",
                inSb: "cat",
                inFile: {
                  nodeUuid: "UUID1",
                  output: "outFile"
                },
                inImage: {
                  nodeUuid: "UUID1",
                  output: "outFile"
                }
              },
              inputNodes: [
                "UUID2",
                "UUID3",
                "UUID1"
              ],
              position: {
                x: 400,
                y: 400
              }
            }
          }
        }, {
          "projectUuid": "89a92ea1-ce5e-488e-9fd8-933a263c6219",
          "name": "3 pipelines",
          "description": "Empty",
          "notes": "Empty",
          "thumbnail": "https://placeimg.com/171/96/tech/grayscale/?25.jpg",
          "owner": "MANUEL",
          "collaborators": {},
          "creationDate": "2018-10-31T12:11:53.179Z",
          "lastChangeDate": "2018-10-31T12:24:32.660Z",
          "workbench": {
            "2e8acead-a59a-42d9-9185-946d428d70b3": {
              "label": "File Picker EM",
              "inputs": {},
              "inputNodes": [],
              "outputNode": false,
              "outputs": {},
              "parent": null,
              "position": {
                "x": 150,
                "y": 150
              },
              "key": "services/dynamic/itis/file-picker",
              "version": "0.0.0"
            },
            "8d603045-bfe8-4822-906c-590fa69c1d13": {
              "label": "isolve-emlf",
              "inputs": {
                "in_1": {
                  "nodeUuid": "2e8acead-a59a-42d9-9185-946d428d70b3",
                  "output": "outFile"
                },
                "NRanks": 1
              },
              "inputNodes": [
                "2e8acead-a59a-42d9-9185-946d428d70b3"
              ],
              "outputNode": false,
              "outputs": {},
              "parent": null,
              "position": {
                "x": 450,
                "y": 150
              },
              "key": "simcore/services/comp/itis/isolve-emlf",
              "version": "0.0.1"
            },
            "08116c6d-2c9e-4939-9c2b-67fe0ae65dc9": {
              "label": "File Picker Neuron",
              "inputs": {},
              "inputNodes": [],
              "outputNode": false,
              "outputs": {},
              "parent": null,
              "position": {
                "x": 150,
                "y": 300
              },
              "key": "services/dynamic/itis/file-picker",
              "version": "0.0.0"
            },
            "1a4aafff-88c7-4e7e-89cc-fe374cfe64ea": {
              "label": "neuron-isolve",
              "inputs": {
                "in_1": {
                  "nodeUuid": "08116c6d-2c9e-4939-9c2b-67fe0ae65dc9",
                  "output": "outFile"
                }
              },
              "inputNodes": [
                "08116c6d-2c9e-4939-9c2b-67fe0ae65dc9"
              ],
              "outputNode": false,
              "outputs": {},
              "parent": null,
              "position": {
                "x": 450,
                "y": 300
              },
              "key": "simcore/services/comp/itis/neuron-isolve",
              "version": "0.0.1"
            },
            "d2d8028c-be3f-473d-a74f-161a286a00ed": {
              "label": "Kember cardiac model",
              "inputs": {
                "dt": 0.01,
                "T": 1000,
                "forcing_factor": 0.0
              },
              "inputNodes": [],
              "outputNode": false,
              "outputs": {},
              "parent": null,
              "position": {
                "x": 150,
                "y": 450
              },
              "key": "simcore/services/comp/kember/cardiac",
              "version": "0.0.2"
            },
            "6cffe7a9-6758-4be6-9988-ec190f4c1d4f": {
              "label": "kember-viewer",
              "inputs": {
                "outputController": {
                  "nodeUuid": "d2d8028c-be3f-473d-a74f-161a286a00ed",
                  "output": "outputController"
                }
              },
              "inputNodes": [
                "d2d8028c-be3f-473d-a74f-161a286a00ed"
              ],
              "outputNode": false,
              "outputs": {},
              "parent": null,
              "position": {
                "x": 450,
                "y": 450
              },
              "key": "simcore/services/dynamic/kember-viewer",
              "version": "1.1.0"
            }
          }
        }, {
          projectUuid: "80363288-84c2-49db-95d1-22e1ea78043e",
          name: "Macros",
          description: "Project containing nested custom macros",
          notes: "# title\nBlah",
          owner: "ODEI",
          collaborators: {
            "ODEI": [
              "read",
              "write"
            ]
          },
          creationDate: "2018-09-24T16:01:00Z",
          lastChangeDate: "2018-09-24T16:02:22Z",
          thumbnail: "https://placeimg.com/171/96/tech/grayscale/?15.jpg",
          workbench: {
            "Sleeper1": {
              key: "services/computational/itis/sleeper",
              version: "0.0.0",
              label: "Sleeper 1",
              inputs: {
                inNumber: 1
              },
              outputs: {
                outNumber: 33
              },
              position: {
                x: 50,
                y: 50
              }
            },
            "Container1": {
              label: "Container 1",
              inputs: {},
              outputs: {},
              inputNodes: [
                "Sleeper1"
              ],
              outputNode: false,
              position: {
                x: 300,
                y: 50
              }
            },
            "Container2": {
              label: "Container 2",
              inputs: {},
              outputs: {},
              inputNodes: [],
              outputNode: false,
              position: {
                x: 50,
                y: 50
              },
              parent: "Container1"
            },
            "Sleeper2": {
              key: "services/computational/itis/sleeper",
              version: "0.0.0",
              inputs: {
                inNumber: 3
              },
              inputNodes: [
                "Container2"
              ],
              position: {
                x: 350,
                y: 50
              },
              parent: "Container1"
            },
            "Sleeper3": {
              key: "services/computational/itis/sleeper",
              version: "0.0.0",
              inputs: {
                inNumber: 2
              },
              position: {
                x: 50,
                y: 50
              },
              parent: "Container2"
            }
          }
        }
      ];
    },

    getPublicProjectList: function() {
      return [
        {
          "projectUuid": "f8000108-2744-41e9-a1a7-f7d4f3a8f26b",
          "name": "Colleen Clancy use cases",
          "description": "All use cases: 0D, 1D, 2D",
          "notes": "Empty",
          "thumbnail": "https://placeimg.com/171/96/tech/grayscale/?18.jpg",
          "owner": "Colleen Clancy",
          "collaborators": {},
          "creationDate": "2018-10-23T09:13:13.360Z",
          "lastChangeDate": "2018-10-23T09:33:41.858Z",
          "workbench": {
            "0b42c964-195d-4674-b758-946151cae351": {
              "label": "File Picker 0D",
              "inputs": {},
              "inputNodes": [],
              "outputNode": false,
              "outputs": {},
              "parent": null,
              "position": {
                "x": 100,
                "y": 150
              },
              "key": "services/dynamic/itis/file-picker",
              "version": "0.0.0"
            },
            "418bd484-905b-4212-8108-c7cfab4f241e": {
              "label": "File Picker 1&2 D",
              "inputs": {},
              "inputNodes": [],
              "outputNode": false,
              "outputs": {},
              "parent": null,
              "position": {
                "x": 100,
                "y": 400
              },
              "key": "services/dynamic/itis/file-picker",
              "version": "0.0.0"
            },
            "Container0D": {
              label: "CC 0D",
              inputs: {},
              outputs: {},
              inputNodes: [
                "0b42c964-195d-4674-b758-946151cae351"
              ],
              outputNode: false,
              position: {
                x: 400,
                y: 50
              }
            },
            "Container1D": {
              label: "CC 1D",
              inputs: {},
              outputs: {},
              inputNodes: [
                "418bd484-905b-4212-8108-c7cfab4f241e"
              ],
              outputNode: false,
              position: {
                x: 400,
                y: 300
              }
            },
            "Container2D": {
              label: "CC 2D",
              inputs: {},
              outputs: {},
              inputNodes: [
                "418bd484-905b-4212-8108-c7cfab4f241e",
                "Container1D"
              ],
              outputNode: false,
              position: {
                x: 700,
                y: 500
              }
            },
            "5986cf64-9f81-409d-998c-c1f04de67f8b": {
              "label": "DBP-Clancy-Rabbit-Single-Cell solver v 0.0.2",
              "inputs": {
                "Na": 0,
                "Kr": 0,
                "BCL": 200,
                "NBeats": 5,
                "Ligand": 0,
                "cAMKII": "WT",
                "initial_WTstates": {
                  "nodeUuid": "0b42c964-195d-4674-b758-946151cae351",
                  "output": "outFile"
                }
              },
              "inputNodes": [
                "0b42c964-195d-4674-b758-946151cae351"
              ],
              "outputNode": false,
              "outputs": {},
              "parent": "Container0D",
              "position": {
                "x": 300,
                "y": 400
              },
              "key": "simcore/services/comp/ucdavis/cardiac-singlecell",
              "version": "0.0.1"
            },
            "00336089-9984-43e7-9fda-cf9625e59986": {
              "label": "cc-0d-viewer",
              "inputs": {
                "vm_1Hz": {
                  "nodeUuid": "5986cf64-9f81-409d-998c-c1f04de67f8b",
                  "output": "vm_1Hz"
                },
                "all_results_1Hz": {
                  "nodeUuid": "5986cf64-9f81-409d-998c-c1f04de67f8b",
                  "output": "allresult_1Hz"
                }
              },
              "inputNodes": [
                "5986cf64-9f81-409d-998c-c1f04de67f8b"
              ],
              "outputNode": false,
              "outputs": {},
              "parent": "Container0D",
              "position": {
                "x": 600,
                "y": 200
              },
              "key": "simcore/services/dynamic/cc-0d-viewer",
              "version": "1.1.0"
            },
            "5e548936-ee08-43f3-ab01-a58e7c49a946": {
              "label": "DBP-Clancy-Rabbit-1-D solver v 0.0.1",
              "inputs": {
                "Na": 0,
                "Kr": 0,
                "BCL": 10,
                "NBeats": 1,
                "Ligand": 0,
                "cAMKII": "WT",
                "tw": 5,
                "tl": 200,
                "homogeneity": "heterogeneous",
                "initial_WTstates": {
                  "nodeUuid": "418bd484-905b-4212-8108-c7cfab4f241e",
                  "output": "outFile"
                }
              },
              "inputNodes": [
                "418bd484-905b-4212-8108-c7cfab4f241e"
              ],
              "outputNode": true,
              "outputs": {},
              "parent": "Container1D",
              "position": {
                "x": 300,
                "y": 400
              },
              "key": "simcore/services/comp/ucdavis/cardiac-oned",
              "version": "0.0.1"
            },
            "c3e872c0-b105-40ce-8d33-7d501a694550": {
              "label": "DBP-Clancy-Rabbit-2-D solver v 0.0.1",
              "inputs": {
                "Na": 0,
                "Kr": 0,
                "BCL": 10,
                "Ligand": 0,
                "cAMKII": "WT",
                "tw": 5,
                "tl": 200,
                "homogeneity": "heterogeneous",
                "initial_WTstates": {
                  "nodeUuid": "418bd484-905b-4212-8108-c7cfab4f241e",
                  "output": "outFile"
                },
                "fiber": {
                  "nodeUuid": "5e548936-ee08-43f3-ab01-a58e7c49a946",
                  "output": "fiber"
                }
              },
              "inputNodes": [
                "418bd484-905b-4212-8108-c7cfab4f241e",
                "Container1"
              ],
              "outputNode": false,
              "outputs": {},
              "parent": "Container2D",
              "position": {
                "x": 300,
                "y": 400
              },
              "key": "simcore/services/comp/ucdavis/cardiac-twod",
              "version": "0.0.1"
            },
            "c354690d-c9c4-47f5-a089-cc4e2eec30b3": {
              "label": "cc-1d-viewer",
              "inputs": {
                "ECGs": "null",
                "y_1D": "null"
              },
              "inputNodes": [
                "5e548936-ee08-43f3-ab01-a58e7c49a946"
              ],
              "outputNode": false,
              "outputs": {},
              "parent": "Container1D",
              "position": {
                "x": 600,
                "y": 200
              },
              "key": "simcore/services/dynamic/cc-1d-viewer",
              "version": "1.1.0"
            },
            "ef9404ef-324f-46b7-825c-6f0f614c54ef": {
              "label": "cc-2d-viewer",
              "inputs": {
                "ap": "null"
              },
              "inputNodes": [
                "c3e872c0-b105-40ce-8d33-7d501a694550"
              ],
              "outputNode": false,
              "outputs": {},
              "parent": "Container2D",
              "position": {
                "x": 600,
                "y": 200
              },
              "key": "simcore/services/dynamic/cc-2d-viewer",
              "version": "1.1.0"
            }
          }
        }, {
          "projectUuid": "61d5829d-426a-49a8-8292-c701530e6e35",
          "name": "Colleen Clancy use cases expanded",
          "description": "All use cases: 0D, 1D, 2D",
          "notes": "Empty",
          "thumbnail": "https://placeimg.com/171/96/tech/grayscale/?18.jpg",
          "owner": "Colleen Clancy",
          "collaborators": {},
          "creationDate": "2018-10-23T09:13:13.360Z",
          "lastChangeDate": "2018-10-23T09:33:41.858Z",
          "workbench": {
            "0b42c964-195d-4674-b758-946151cae351": {
              "label": "File Picker",
              "inputs": {},
              "inputNodes": [],
              "outputNode": false,
              "outputs": {},
              "parent": null,
              "position": {
                "x": 108,
                "y": 131
              },
              "key": "services/dynamic/itis/file-picker",
              "version": "0.0.0"
            },
            "5986cf64-9f81-409d-998c-c1f04de67f8b": {
              "label": "DBP-Clancy-Rabbit-Single-Cell solver v 0.0.2",
              "inputs": {
                "Na": 0,
                "Kr": 0,
                "BCL": 200,
                "NBeats": 5,
                "Ligand": 0,
                "cAMKII": "WT",
                "initial_WTstates": {
                  "nodeUuid": "0b42c964-195d-4674-b758-946151cae351",
                  "output": "outFile"
                }
              },
              "inputNodes": [
                "0b42c964-195d-4674-b758-946151cae351"
              ],
              "outputNode": false,
              "outputs": {},
              "parent": null,
              "position": {
                "x": 393,
                "y": 131
              },
              "key": "simcore/services/comp/ucdavis/cardiac-singlecell",
              "version": "0.0.1"
            },
            "00336089-9984-43e7-9fda-cf9625e59986": {
              "label": "cc-0d-viewer",
              "inputs": {
                "vm_1Hz": {
                  "nodeUuid": "5986cf64-9f81-409d-998c-c1f04de67f8b",
                  "output": "vm_1Hz"
                },
                "all_results_1Hz": {
                  "nodeUuid": "5986cf64-9f81-409d-998c-c1f04de67f8b",
                  "output": "allresult_1Hz"
                }
              },
              "inputNodes": [
                "5986cf64-9f81-409d-998c-c1f04de67f8b"
              ],
              "outputNode": false,
              "outputs": {},
              "parent": null,
              "position": {
                "x": 681,
                "y": 131
              },
              "key": "simcore/services/dynamic/cc-0d-viewer",
              "version": "1.1.0"
            },
            "418bd484-905b-4212-8108-c7cfab4f241e": {
              "label": "File Picker",
              "inputs": {},
              "inputNodes": [],
              "outputNode": false,
              "outputs": {},
              "parent": null,
              "position": {
                "x": 100,
                "y": 429
              },
              "key": "services/dynamic/itis/file-picker",
              "version": "0.0.0"
            },
            "5e548936-ee08-43f3-ab01-a58e7c49a946": {
              "label": "DBP-Clancy-Rabbit-1-D solver v 0.0.1",
              "inputs": {
                "Na": 0,
                "Kr": 0,
                "BCL": 10,
                "NBeats": 1,
                "Ligand": 0,
                "cAMKII": "WT",
                "tw": 5,
                "tl": 200,
                "homogeneity": "heterogeneous",
                "initial_WTstates": {
                  "nodeUuid": "418bd484-905b-4212-8108-c7cfab4f241e",
                  "output": "outFile"
                }
              },
              "inputNodes": [
                "418bd484-905b-4212-8108-c7cfab4f241e"
              ],
              "outputNode": false,
              "outputs": {},
              "parent": null,
              "position": {
                "x": 363,
                "y": 346
              },
              "key": "simcore/services/comp/ucdavis/cardiac-oned",
              "version": "0.0.1"
            },
            "c3e872c0-b105-40ce-8d33-7d501a694550": {
              "label": "DBP-Clancy-Rabbit-2-D solver v 0.0.1",
              "inputs": {
                "Na": 0,
                "Kr": 0,
                "BCL": 10,
                "Ligand": 0,
                "cAMKII": "WT",
                "tw": 5,
                "tl": 200,
                "homogeneity": "heterogeneous",
                "initial_WTstates": {
                  "nodeUuid": "418bd484-905b-4212-8108-c7cfab4f241e",
                  "output": "outFile"
                },
                "fiber": {
                  "nodeUuid": "5e548936-ee08-43f3-ab01-a58e7c49a946",
                  "output": "fiber"
                }
              },
              "inputNodes": [
                "418bd484-905b-4212-8108-c7cfab4f241e",
                "5e548936-ee08-43f3-ab01-a58e7c49a946"
              ],
              "outputNode": false,
              "outputs": {},
              "parent": null,
              "position": {
                "x": 603,
                "y": 517
              },
              "key": "simcore/services/comp/ucdavis/cardiac-twod",
              "version": "0.0.1"
            },
            "c354690d-c9c4-47f5-a089-cc4e2eec30b3": {
              "label": "cc-1d-viewer",
              "inputs": {
                "ECGs": "null",
                "y_1D": "null"
              },
              "inputNodes": [
                "5e548936-ee08-43f3-ab01-a58e7c49a946"
              ],
              "outputNode": false,
              "outputs": {},
              "parent": null,
              "position": {
                "x": 844,
                "y": 348
              },
              "key": "simcore/services/dynamic/cc-1d-viewer",
              "version": "1.1.0"
            },
            "ef9404ef-324f-46b7-825c-6f0f614c54ef": {
              "label": "cc-2d-viewer",
              "inputs": {
                "ap": "null"
              },
              "inputNodes": [
                "c3e872c0-b105-40ce-8d33-7d501a694550"
              ],
              "outputNode": false,
              "outputs": {},
              "parent": null,
              "position": {
                "x": 850,
                "y": 517
              },
              "key": "simcore/services/dynamic/cc-2d-viewer",
              "version": "1.1.0"
            }
          }
        }, {
          projectUuid: "345a37ab-5346-4983-951a-19ba2ef9ca0f",
          name: "LF Simulator",
          description: "LF Simulator",
          notes: "",
          owner: "ODEI",
          collaborators: {
            "ODEI": [
              "read",
              "write"
            ]
          },
          creationDate: "2018-07-08T16:01:00Z",
          lastChangeDate: "2018-07-09T16:02:22Z",
          thumbnail: "https://placeimg.com/171/96/tech/grayscale/?8.jpg",
          workbench: {
            "c104bb08-77b1-4157-b9f9-e9df7779df08": {
              key: "services/demodec/dynamic/itis/s4l/Modeler",
              version: "0.0.0",
              label: "Modeler 1",
              position: {
                x: 50,
                y: 50
              }
            },
            "bf88496d-ddf8-476c-8d6c-24c716c2ae4c": {
              key: "services/demodec/dynamic/itis/s4l/MaterialDB",
              version: "0.0.0",
              label: "Material DB 1",
              position: {
                x: 50,
                y: 300
              }
            },
            "89e185ca-dda1-4a45-8059-715f2cb17100": {
              label: "LF Simulator Container",
              position: {
                x: 400,
                y: 150
              },
              inputs: {},
              outputs: {},
              inputNodes: [
                "bf88496d-ddf8-476c-8d6c-24c716c2ae4c",
                "c104bb08-77b1-4157-b9f9-e9df7779df08"
              ],
              outputNode: false
            },
            "SetupId": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Setup",
              version: "0.0.0",
              label: "LF Setup 1",
              inputNodes: [],
              outputNode: false,
              position: {
                x: 100,
                y: 50
              },
              parent: "89e185ca-dda1-4a45-8059-715f2cb17100"
            },
            "MaterialsId": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Materials",
              version: "0.0.0",
              label: "LF Materials 1",
              inputNodes: [
                "c104bb08-77b1-4157-b9f9-e9df7779df08",
                "bf88496d-ddf8-476c-8d6c-24c716c2ae4c"
              ],
              outputNode: false,
              position: {
                x: 100,
                y: 150
              },
              parent: "89e185ca-dda1-4a45-8059-715f2cb17100"
            },
            "BoundaryId": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Boundary",
              version: "0.0.0",
              label: "LF Boundary 1",
              inputNodes: [
                "c104bb08-77b1-4157-b9f9-e9df7779df08"
              ],
              outputNode: false,
              position: {
                x: 100,
                y: 250
              },
              parent: "89e185ca-dda1-4a45-8059-715f2cb17100"
            },
            "SensorsId": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Sensors",
              version: "0.0.0",
              label: "LF Sensors 1",
              inputNodes: [
                "c104bb08-77b1-4157-b9f9-e9df7779df08"
              ],
              outputNode: true,
              position: {
                x: 100,
                y: 350
              },
              parent: "89e185ca-dda1-4a45-8059-715f2cb17100"
            },
            "GridId": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Grid",
              version: "0.0.0",
              label: "LF Grid 1",
              inputNodes: [
                "c104bb08-77b1-4157-b9f9-e9df7779df08"
              ],
              outputNode: false,
              position: {
                x: 100,
                y: 450
              },
              parent: "89e185ca-dda1-4a45-8059-715f2cb17100"
            },
            "VoxelId": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Voxel",
              version: "0.0.0",
              label: "LF Voxel 1",
              inputNodes: [
                "c104bb08-77b1-4157-b9f9-e9df7779df08"
              ],
              outputNode: false,
              position: {
                x: 100,
                y: 550
              },
              parent: "89e185ca-dda1-4a45-8059-715f2cb17100"
            },
            "SolverSettingsId": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/LF/SolverSettings",
              version: "0.0.0",
              label: "LF SolverSett 1",
              inputNodes: [],
              outputNode: true,
              position: {
                x: 500,
                y: 250
              },
              parent: "89e185ca-dda1-4a45-8059-715f2cb17100"
            },
            "4069bf2e-e2be-4799-ad1c-c53f0cb46e4e": {
              key: "services/computational/itis/Solver-LF",
              version: "0.0.0",
              label: "LF Solver 1",
              inputs: {
                inFile: {
                  nodeUuid: "89e185ca-dda1-4a45-8059-715f2cb17100",
                  output: "outFile"
                }
              },
              inputNodes: [
                "89e185ca-dda1-4a45-8059-715f2cb17100"
              ],
              position: {
                x: 750,
                y: 150
              }
            }
          }
        }, {
          projectUuid: "5a1d7405-882c-4611-a74c-4c75f3cf7749",
          name: "LF Simulator expanded",
          description: "LF Simulator expanded",
          notes: "",
          owner: "ODEI",
          collaborators: {
            "ODEI": [
              "read",
              "write"
            ]
          },
          creationDate: "2018-08-31T12:44:03Z",
          lastChangeDate: "2018-08-31T13:21:24Z",
          thumbnail: "https://placeimg.com/171/96/tech/grayscale/?3.jpg",
          workbench: {
            "8870a55b-680d-41b4-b40c-c928cceb7d2a": {
              key: "services/demodec/dynamic/itis/s4l/MaterialDB",
              version: "0.0.0",
              position: {
                x: 10,
                y: 160
              }
            },
            "17a932a0-f401-4571-9c55-b579f5050d37": {
              key: "services/demodec/dynamic/itis/s4l/Modeler",
              version: "0.0.0",
              position: {
                x: 7,
                y: 538
              }
            },
            "83bc4123-ebe4-4f5f-8770-b1584d6cf95f": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Setup",
              version: "0.0.0",
              inputs: {
                "frequency": 1000
              },
              position: {
                x: 348,
                y: 2
              }
            },
            "ac80863e-e4ef-48c0-804b-d9296f1f3563": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Materials",
              version: "0.0.0",
              inputs: {
                "updateDispersive": false
              },
              inputNodes: [
                "17a932a0-f401-4571-9c55-b579f5050d37",
                "8870a55b-680d-41b4-b40c-c928cceb7d2a"
              ],
              position: {
                x: 349,
                y: 103
              }
            },
            "ed4c85a8-c20f-4acd-8e1e-5161301e2f3d": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Boundary",
              version: "0.0.0",
              inputNodes: [
                "17a932a0-f401-4571-9c55-b579f5050d37"
              ],
              position: {
                x: 351,
                y: 242
              }
            },
            "36d70cf2-ef36-4052-988d-d32b3456b786": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Sensors",
              version: "0.0.0",
              inputs: {
                "sensorSetting": 4
              },
              inputNodes: [
                "17a932a0-f401-4571-9c55-b579f5050d37"
              ],
              position: {
                x: 353,
                y: 363
              }
            },
            "c3ab33a7-4ead-4302-9867-5b194a4f45ec": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Grid",
              version: "0.0.0",
              inputs: {
                "gridSetting": 5
              },
              inputNodes: [
                "17a932a0-f401-4571-9c55-b579f5050d37",
                "ac80863e-e4ef-48c0-804b-d9296f1f3563",
                "ed4c85a8-c20f-4acd-8e1e-5161301e2f3d",
                "36d70cf2-ef36-4052-988d-d32b3456b786"
              ],
              position: {
                x: 624,
                y: 496
              }
            },
            "01e28708-46c4-474b-837b-479fd596e566": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/LF/SolverSettings",
              version: "0.0.0",
              inputs: {
                "solverSetting": 7
              },
              inputNodes: [
                "83bc4123-ebe4-4f5f-8770-b1584d6cf95f",
                "b37bea52-bb29-482a-9540-bc11c7dc779c"
              ],
              position: {
                x: 955,
                y: 318
              }
            },
            "b37bea52-bb29-482a-9540-bc11c7dc779c": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Voxel",
              version: "0.0.0",
              inputs: {
                "voxelSetting": 6
              },
              inputNodes: [
                "17a932a0-f401-4571-9c55-b579f5050d37",
                "c3ab33a7-4ead-4302-9867-5b194a4f45ec"
              ],
              position: {
                x: 874,
                y: 699
              }
            },
            "2472a166-7a9e-4023-be12-465d2f6eee54": {
              key: "services/computational/itis/Solver-LF",
              version: "0.0.0",
              inputs: {
                "inFile": {
                  nodeUuid: "01e28708-46c4-474b-837b-479fd596e566",
                  output: "outFile"
                }
              },
              inputNodes: [
                "01e28708-46c4-474b-837b-479fd596e566"
              ],
              position: {
                x: 1245,
                y: 318
              }
            }
          }
        }, {
          projectUuid: "1d4269a4-0fbc-4bf9-9eb3-11356a46c45a",
          name: "Demo December",
          description: "",
          notes: "",
          owner: "ODEI",
          collaborators: {
            "ODEI": [
              "read",
              "write"
            ]
          },
          creationDate: "2018-07-08T16:01:00Z",
          lastChangeDate: "2018-07-09T16:02:22Z",
          thumbnail: "https://placeimg.com/171/96/tech/grayscale/?2.jpg",
          workbench: {
            "c104bb08-77b1-4157-b9f9-e9df7779df08": {
              key: "services/demodec/dynamic/itis/s4l/Modeler",
              version: "0.0.0",
              label: "Modeler",
              position: {
                x: 50,
                y: 300
              }
            },
            "bf88496d-ddf8-476c-8d6c-24c716c2ae4c": {
              key: "services/demodec/dynamic/itis/s4l/MaterialDB",
              version: "0.0.0",
              label: "Material DB",
              position: {
                x: 50,
                y: 50
              }
            },
            "89e185ca-dda1-4a45-8059-715f2cb17100": {
              label: "LF Simulator Container",
              position: {
                x: 300,
                y: 150
              },
              inputs: {},
              outputs: {},
              inputNodes: [
                "bf88496d-ddf8-476c-8d6c-24c716c2ae4c",
                "c104bb08-77b1-4157-b9f9-e9df7779df08"
              ],
              outputNode: false
            },
            "SetupId": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Setup",
              version: "0.0.0",
              label: "LF Setup 1",
              inputNodes: [],
              outputNode: false,
              position: {
                x: 100,
                y: 50
              },
              parent: "89e185ca-dda1-4a45-8059-715f2cb17100"
            },
            "MaterialsId": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Materials",
              version: "0.0.0",
              label: "LF Materials 1",
              inputNodes: [
                "c104bb08-77b1-4157-b9f9-e9df7779df08",
                "bf88496d-ddf8-476c-8d6c-24c716c2ae4c"
              ],
              outputNode: false,
              position: {
                x: 100,
                y: 150
              },
              parent: "89e185ca-dda1-4a45-8059-715f2cb17100"
            },
            "BoundaryId": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Boundary",
              version: "0.0.0",
              label: "LF Boundary 1",
              inputNodes: [
                "c104bb08-77b1-4157-b9f9-e9df7779df08"
              ],
              outputNode: false,
              position: {
                x: 100,
                y: 250
              },
              parent: "89e185ca-dda1-4a45-8059-715f2cb17100"
            },
            "SensorsId": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Sensors",
              version: "0.0.0",
              label: "LF Sensors 1",
              inputNodes: [
                "c104bb08-77b1-4157-b9f9-e9df7779df08"
              ],
              outputNode: true,
              position: {
                x: 100,
                y: 350
              },
              parent: "89e185ca-dda1-4a45-8059-715f2cb17100"
            },
            "GridId": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Grid",
              version: "0.0.0",
              label: "LF Grid 1",
              inputNodes: [
                "c104bb08-77b1-4157-b9f9-e9df7779df08"
              ],
              outputNode: false,
              position: {
                x: 100,
                y: 450
              },
              parent: "89e185ca-dda1-4a45-8059-715f2cb17100"
            },
            "VoxelId": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/LF/Voxel",
              version: "0.0.0",
              label: "LF Voxel 1",
              inputNodes: [
                "c104bb08-77b1-4157-b9f9-e9df7779df08"
              ],
              outputNode: false,
              position: {
                x: 100,
                y: 550
              },
              parent: "89e185ca-dda1-4a45-8059-715f2cb17100"
            },
            "SolverSettingsId": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/LF/SolverSettings",
              version: "0.0.0",
              label: "LF SolverSett 1",
              inputNodes: [],
              position: {
                x: 400,
                y: 250
              },
              parent: "89e185ca-dda1-4a45-8059-715f2cb17100"
            },
            "4069bf2e-e2be-4799-ad1c-c53f0cb46e4e": {
              key: "simcore/services/comp/itis/isolve-emlf",
              version: "0.0.1",
              label: "EM-LF Solver",
              inputs: {
                "in_1": {
                  nodeUuid: "SolverSettingsId",
                  output: "outFile"
                }
              },
              inputNodes: [
                "SolverSettingsId"
              ],
              outputNode: true,
              position: {
                x: 650,
                y: 250
              },
              parent: "89e185ca-dda1-4a45-8059-715f2cb17100"
            },
            "96343608-610b-4951-89af-4b189e5e3861": {
              label: "Neuron Simulator Container",
              position: {
                x: 500,
                y: 450
              },
              inputs: {},
              outputs: {},
              inputNodes: [
                "c104bb08-77b1-4157-b9f9-e9df7779df08",
                "89e185ca-dda1-4a45-8059-715f2cb17100"
              ],
              outputNode: false
            },
            "SetupId2": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/Neuron/Setup",
              version: "0.0.0",
              label: "Neuron Setup",
              inputNodes: [],
              outputNode: false,
              position: {
                x: 100,
                y: 50
              },
              parent: "96343608-610b-4951-89af-4b189e5e3861"
            },
            "MaterialsId2": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/Neuron/Materials",
              version: "0.0.0",
              label: "Neurons",
              inputNodes: [
                "c104bb08-77b1-4157-b9f9-e9df7779df08",
                "bf88496d-ddf8-476c-8d6c-24c716c2ae4c"
              ],
              outputNode: true,
              position: {
                x: 100,
                y: 150
              },
              parent: "96343608-610b-4951-89af-4b189e5e3861"
            },
            "SensorsId2": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/Neuron/Sensors",
              version: "0.0.0",
              label: "Neuron Sensors",
              inputNodes: [
                "c104bb08-77b1-4157-b9f9-e9df7779df08"
              ],
              outputNode: true,
              position: {
                x: 100,
                y: 350
              },
              parent: "96343608-610b-4951-89af-4b189e5e3861"
            },
            "SolverSettingsId2": {
              key: "services/demodec/dynamic/itis/s4l/Simulator/Neuron/SolverSettings",
              version: "0.0.0",
              label: "Neuron SolverSett",
              inputNodes: [],
              outputNode: true,
              position: {
                x: 400,
                y: 250
              },
              parent: "96343608-610b-4951-89af-4b189e5e3861"
            },
            "da1ccae6-70cd-4c90-94a4-c43fab9b10f7": {
              key: "simcore/services/comp/itis/neuron-isolve",
              version: "0.0.1",
              label: "Neuron Solver",
              inputs: {
                "in_1": {
                  nodeUuid: "SolverSettingsId2",
                  output: "outFile"
                }
              },
              inputNodes: [
                "SolverSettingsId2"
              ],
              position: {
                x: 650,
                y: 250
              },
              parent: "96343608-610b-4951-89af-4b189e5e3861"
            }
          }
        }
      ];
    },

    getProjectList: function() {
      let userList = this.getUserProjectList();
      let publicList = this.getPublicProjectList();
      return userList.concat(publicList);
    },

    getProjectData: function(projectUuid) {
      const projectList = this.getProjectList();
      for (let i = 0; i < projectList.length; i++) {
        if (projectUuid === projectList[i].projectUuid) {
          return projectList[i];
        }
      }
      return null;
    },

    getObjectList: function() {
      const objects = [{
        "file_uuid": "103/10002/0",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "103/10002/0",
        "project_id": "103",
        "project_name": "dermatology",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "0",
        "user_id": "10",
        "user_name": "alice"
      },
      {
        "file_uuid": "106/10003/2",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "106/10003/2",
        "project_id": "106",
        "project_name": "geology",
        "node_id": "10003",
        "node_name": "delta",
        "file_name": "2",
        "user_id": "10",
        "user_name": "alice"
      },
      {
        "file_uuid": "104/10002/4",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "104/10002/4",
        "project_id": "104",
        "project_name": "economics",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "4",
        "user_id": "10",
        "user_name": "alice"
      },
      {
        "file_uuid": "101/10003/22",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "101/10003/22",
        "project_id": "101",
        "project_name": "biology",
        "node_id": "10003",
        "node_name": "delta",
        "file_name": "22",
        "user_id": "10",
        "user_name": "alice"
      },
      {
        "file_uuid": "103/10003/32",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "103/10003/32",
        "project_id": "103",
        "project_name": "dermatology",
        "node_id": "10003",
        "node_name": "delta",
        "file_name": "32",
        "user_id": "10",
        "user_name": "alice"
      },
      {
        "file_uuid": "103/10003/48",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "103/10003/48",
        "project_id": "103",
        "project_name": "dermatology",
        "node_id": "10003",
        "node_name": "delta",
        "file_name": "48",
        "user_id": "10",
        "user_name": "alice"
      },
      {
        "file_uuid": "106/10002/49",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "106/10002/49",
        "project_id": "106",
        "project_name": "geology",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "49",
        "user_id": "10",
        "user_name": "alice"
      },
      {
        "file_uuid": "103/10000/54",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "103/10000/54",
        "project_id": "103",
        "project_name": "dermatology",
        "node_id": "10000",
        "node_name": "alpha",
        "file_name": "54",
        "user_id": "10",
        "user_name": "alice"
      },
      {
        "file_uuid": "106/10002/56",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "106/10002/56",
        "project_id": "106",
        "project_name": "geology",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "56",
        "user_id": "10",
        "user_name": "alice"
      },
      {
        "file_uuid": "100/10002/64",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "100/10002/64",
        "project_id": "100",
        "project_name": "astronomy",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "64",
        "user_id": "10",
        "user_name": "alice"
      },
      {
        "file_uuid": "105/10003/70",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "105/10003/70",
        "project_id": "105",
        "project_name": "futurology",
        "node_id": "10003",
        "node_name": "delta",
        "file_name": "70",
        "user_id": "10",
        "user_name": "alice"
      },
      {
        "file_uuid": "102/10003/72",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "102/10003/72",
        "project_id": "102",
        "project_name": "chemistry",
        "node_id": "10003",
        "node_name": "delta",
        "file_name": "72",
        "user_id": "10",
        "user_name": "alice"
      },
      {
        "file_uuid": "106/10000/73",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "106/10000/73",
        "project_id": "106",
        "project_name": "geology",
        "node_id": "10000",
        "node_name": "alpha",
        "file_name": "73",
        "user_id": "10",
        "user_name": "alice"
      },
      {
        "file_uuid": "102/10001/76",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "102/10001/76",
        "project_id": "102",
        "project_name": "chemistry",
        "node_id": "10001",
        "node_name": "beta",
        "file_name": "76",
        "user_id": "10",
        "user_name": "alice"
      },
      {
        "file_uuid": "105/10000/79",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "105/10000/79",
        "project_id": "105",
        "project_name": "futurology",
        "node_id": "10000",
        "node_name": "alpha",
        "file_name": "79",
        "user_id": "10",
        "user_name": "alice"
      },
      {
        "file_uuid": "101/10002/81",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "101/10002/81",
        "project_id": "101",
        "project_name": "biology",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "81",
        "user_id": "10",
        "user_name": "alice"
      },
      {
        "file_uuid": "104/10001/83",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "104/10001/83",
        "project_id": "104",
        "project_name": "economics",
        "node_id": "10001",
        "node_name": "beta",
        "file_name": "83",
        "user_id": "10",
        "user_name": "alice"
      },
      {
        "file_uuid": "102/10001/85",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "102/10001/85",
        "project_id": "102",
        "project_name": "chemistry",
        "node_id": "10001",
        "node_name": "beta",
        "file_name": "85",
        "user_id": "10",
        "user_name": "alice"
      },
      {
        "file_uuid": "102/10001/88",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "102/10001/88",
        "project_id": "102",
        "project_name": "chemistry",
        "node_id": "10001",
        "node_name": "beta",
        "file_name": "88",
        "user_id": "10",
        "user_name": "alice"
      },
      {
        "file_uuid": "100/10002/94",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "100/10002/94",
        "project_id": "100",
        "project_name": "astronomy",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "94",
        "user_id": "10",
        "user_name": "alice"
      },
      {
        "file_uuid": "102/10002/95",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "102/10002/95",
        "project_id": "102",
        "project_name": "chemistry",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "95",
        "user_id": "10",
        "user_name": "alice"
      },
      {
        "file_uuid": "103/10001/98",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "103/10001/98",
        "project_id": "103",
        "project_name": "dermatology",
        "node_id": "10001",
        "node_name": "beta",
        "file_name": "98",
        "user_id": "10",
        "user_name": "alice"
      },
      {
        "file_uuid": "105/10003/1",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "105/10003/1",
        "project_id": "105",
        "project_name": "futurology",
        "node_id": "10003",
        "node_name": "delta",
        "file_name": "1",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "106/10000/3",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "106/10000/3",
        "project_id": "106",
        "project_name": "geology",
        "node_id": "10000",
        "node_name": "alpha",
        "file_name": "3",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "102/10001/6",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "102/10001/6",
        "project_id": "102",
        "project_name": "chemistry",
        "node_id": "10001",
        "node_name": "beta",
        "file_name": "6",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "100/10001/11",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "100/10001/11",
        "project_id": "100",
        "project_name": "astronomy",
        "node_id": "10001",
        "node_name": "beta",
        "file_name": "11",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "105/10000/12",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "105/10000/12",
        "project_id": "105",
        "project_name": "futurology",
        "node_id": "10000",
        "node_name": "alpha",
        "file_name": "12",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "102/10001/15",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "102/10001/15",
        "project_id": "102",
        "project_name": "chemistry",
        "node_id": "10001",
        "node_name": "beta",
        "file_name": "15",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "100/10001/19",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "100/10001/19",
        "project_id": "100",
        "project_name": "astronomy",
        "node_id": "10001",
        "node_name": "beta",
        "file_name": "19",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "104/10003/23",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "104/10003/23",
        "project_id": "104",
        "project_name": "economics",
        "node_id": "10003",
        "node_name": "delta",
        "file_name": "23",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "102/10001/27",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "102/10001/27",
        "project_id": "102",
        "project_name": "chemistry",
        "node_id": "10001",
        "node_name": "beta",
        "file_name": "27",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "103/10000/29",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "103/10000/29",
        "project_id": "103",
        "project_name": "dermatology",
        "node_id": "10000",
        "node_name": "alpha",
        "file_name": "29",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "104/10001/30",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "104/10001/30",
        "project_id": "104",
        "project_name": "economics",
        "node_id": "10001",
        "node_name": "beta",
        "file_name": "30",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "106/10000/35",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "106/10000/35",
        "project_id": "106",
        "project_name": "geology",
        "node_id": "10000",
        "node_name": "alpha",
        "file_name": "35",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "104/10003/36",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "104/10003/36",
        "project_id": "104",
        "project_name": "economics",
        "node_id": "10003",
        "node_name": "delta",
        "file_name": "36",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "103/10001/37",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "103/10001/37",
        "project_id": "103",
        "project_name": "dermatology",
        "node_id": "10001",
        "node_name": "beta",
        "file_name": "37",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "104/10000/40",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "104/10000/40",
        "project_id": "104",
        "project_name": "economics",
        "node_id": "10000",
        "node_name": "alpha",
        "file_name": "40",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "106/10003/41",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "106/10003/41",
        "project_id": "106",
        "project_name": "geology",
        "node_id": "10003",
        "node_name": "delta",
        "file_name": "41",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "103/10003/42",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "103/10003/42",
        "project_id": "103",
        "project_name": "dermatology",
        "node_id": "10003",
        "node_name": "delta",
        "file_name": "42",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "103/10003/43",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "103/10003/43",
        "project_id": "103",
        "project_name": "dermatology",
        "node_id": "10003",
        "node_name": "delta",
        "file_name": "43",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "104/10003/44",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "104/10003/44",
        "project_id": "104",
        "project_name": "economics",
        "node_id": "10003",
        "node_name": "delta",
        "file_name": "44",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "100/10002/57",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "100/10002/57",
        "project_id": "100",
        "project_name": "astronomy",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "57",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "104/10000/58",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "104/10000/58",
        "project_id": "104",
        "project_name": "economics",
        "node_id": "10000",
        "node_name": "alpha",
        "file_name": "58",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "104/10000/61",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "104/10000/61",
        "project_id": "104",
        "project_name": "economics",
        "node_id": "10000",
        "node_name": "alpha",
        "file_name": "61",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "103/10003/63",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "103/10003/63",
        "project_id": "103",
        "project_name": "dermatology",
        "node_id": "10003",
        "node_name": "delta",
        "file_name": "63",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "100/10002/71",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "100/10002/71",
        "project_id": "100",
        "project_name": "astronomy",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "71",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "104/10002/75",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "104/10002/75",
        "project_id": "104",
        "project_name": "economics",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "75",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "101/10002/77",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "101/10002/77",
        "project_id": "101",
        "project_name": "biology",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "77",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "103/10003/78",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "103/10003/78",
        "project_id": "103",
        "project_name": "dermatology",
        "node_id": "10003",
        "node_name": "delta",
        "file_name": "78",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "106/10003/84",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "106/10003/84",
        "project_id": "106",
        "project_name": "geology",
        "node_id": "10003",
        "node_name": "delta",
        "file_name": "84",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "105/10002/89",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "105/10002/89",
        "project_id": "105",
        "project_name": "futurology",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "89",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "105/10003/90",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "105/10003/90",
        "project_id": "105",
        "project_name": "futurology",
        "node_id": "10003",
        "node_name": "delta",
        "file_name": "90",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "101/10002/99",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "101/10002/99",
        "project_id": "101",
        "project_name": "biology",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "99",
        "user_id": "13",
        "user_name": "dennis"
      },
      {
        "file_uuid": "103/10003/5",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "103/10003/5",
        "project_id": "103",
        "project_name": "dermatology",
        "node_id": "10003",
        "node_name": "delta",
        "file_name": "5",
        "user_id": "11",
        "user_name": "bob"
      },
      {
        "file_uuid": "106/10003/9",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "106/10003/9",
        "project_id": "106",
        "project_name": "geology",
        "node_id": "10003",
        "node_name": "delta",
        "file_name": "9",
        "user_id": "11",
        "user_name": "bob"
      },
      {
        "file_uuid": "105/10000/14",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "105/10000/14",
        "project_id": "105",
        "project_name": "futurology",
        "node_id": "10000",
        "node_name": "alpha",
        "file_name": "14",
        "user_id": "11",
        "user_name": "bob"
      },
      {
        "file_uuid": "105/10002/21",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "105/10002/21",
        "project_id": "105",
        "project_name": "futurology",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "21",
        "user_id": "11",
        "user_name": "bob"
      },
      {
        "file_uuid": "105/10002/25",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "105/10002/25",
        "project_id": "105",
        "project_name": "futurology",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "25",
        "user_id": "11",
        "user_name": "bob"
      },
      {
        "file_uuid": "103/10002/31",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "103/10002/31",
        "project_id": "103",
        "project_name": "dermatology",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "31",
        "user_id": "11",
        "user_name": "bob"
      },
      {
        "file_uuid": "106/10000/34",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "106/10000/34",
        "project_id": "106",
        "project_name": "geology",
        "node_id": "10000",
        "node_name": "alpha",
        "file_name": "34",
        "user_id": "11",
        "user_name": "bob"
      },
      {
        "file_uuid": "103/10002/45",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "103/10002/45",
        "project_id": "103",
        "project_name": "dermatology",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "45",
        "user_id": "11",
        "user_name": "bob"
      },
      {
        "file_uuid": "104/10001/47",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "104/10001/47",
        "project_id": "104",
        "project_name": "economics",
        "node_id": "10001",
        "node_name": "beta",
        "file_name": "47",
        "user_id": "11",
        "user_name": "bob"
      },
      {
        "file_uuid": "105/10002/51",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "105/10002/51",
        "project_id": "105",
        "project_name": "futurology",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "51",
        "user_id": "11",
        "user_name": "bob"
      },
      {
        "file_uuid": "105/10002/53",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "105/10002/53",
        "project_id": "105",
        "project_name": "futurology",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "53",
        "user_id": "11",
        "user_name": "bob"
      },
      {
        "file_uuid": "102/10002/55",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "102/10002/55",
        "project_id": "102",
        "project_name": "chemistry",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "55",
        "user_id": "11",
        "user_name": "bob"
      },
      {
        "file_uuid": "105/10000/59",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "105/10000/59",
        "project_id": "105",
        "project_name": "futurology",
        "node_id": "10000",
        "node_name": "alpha",
        "file_name": "59",
        "user_id": "11",
        "user_name": "bob"
      },
      {
        "file_uuid": "101/10001/60",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "101/10001/60",
        "project_id": "101",
        "project_name": "biology",
        "node_id": "10001",
        "node_name": "beta",
        "file_name": "60",
        "user_id": "11",
        "user_name": "bob"
      },
      {
        "file_uuid": "106/10001/62",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "106/10001/62",
        "project_id": "106",
        "project_name": "geology",
        "node_id": "10001",
        "node_name": "beta",
        "file_name": "62",
        "user_id": "11",
        "user_name": "bob"
      },
      {
        "file_uuid": "100/10002/65",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "100/10002/65",
        "project_id": "100",
        "project_name": "astronomy",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "65",
        "user_id": "11",
        "user_name": "bob"
      },
      {
        "file_uuid": "103/10000/67",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "103/10000/67",
        "project_id": "103",
        "project_name": "dermatology",
        "node_id": "10000",
        "node_name": "alpha",
        "file_name": "67",
        "user_id": "11",
        "user_name": "bob"
      },
      {
        "file_uuid": "104/10000/69",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "104/10000/69",
        "project_id": "104",
        "project_name": "economics",
        "node_id": "10000",
        "node_name": "alpha",
        "file_name": "69",
        "user_id": "11",
        "user_name": "bob"
      },
      {
        "file_uuid": "101/10000/74",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "101/10000/74",
        "project_id": "101",
        "project_name": "biology",
        "node_id": "10000",
        "node_name": "alpha",
        "file_name": "74",
        "user_id": "11",
        "user_name": "bob"
      },
      {
        "file_uuid": "101/10000/86",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "101/10000/86",
        "project_id": "101",
        "project_name": "biology",
        "node_id": "10000",
        "node_name": "alpha",
        "file_name": "86",
        "user_id": "11",
        "user_name": "bob"
      },
      {
        "file_uuid": "106/10001/91",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "106/10001/91",
        "project_id": "106",
        "project_name": "geology",
        "node_id": "10001",
        "node_name": "beta",
        "file_name": "91",
        "user_id": "11",
        "user_name": "bob"
      },
      {
        "file_uuid": "103/10003/93",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "103/10003/93",
        "project_id": "103",
        "project_name": "dermatology",
        "node_id": "10003",
        "node_name": "delta",
        "file_name": "93",
        "user_id": "11",
        "user_name": "bob"
      },
      {
        "file_uuid": "102/10002/96",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "102/10002/96",
        "project_id": "102",
        "project_name": "chemistry",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "96",
        "user_id": "11",
        "user_name": "bob"
      },
      {
        "file_uuid": "104/10003/7",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "104/10003/7",
        "project_id": "104",
        "project_name": "economics",
        "node_id": "10003",
        "node_name": "delta",
        "file_name": "7",
        "user_id": "12",
        "user_name": "chuck"
      },
      {
        "file_uuid": "106/10002/8",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "106/10002/8",
        "project_id": "106",
        "project_name": "geology",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "8",
        "user_id": "12",
        "user_name": "chuck"
      },
      {
        "file_uuid": "103/10002/10",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "103/10002/10",
        "project_id": "103",
        "project_name": "dermatology",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "10",
        "user_id": "12",
        "user_name": "chuck"
      },
      {
        "file_uuid": "100/10003/13",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "100/10003/13",
        "project_id": "100",
        "project_name": "astronomy",
        "node_id": "10003",
        "node_name": "delta",
        "file_name": "13",
        "user_id": "12",
        "user_name": "chuck"
      },
      {
        "file_uuid": "103/10003/16",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "103/10003/16",
        "project_id": "103",
        "project_name": "dermatology",
        "node_id": "10003",
        "node_name": "delta",
        "file_name": "16",
        "user_id": "12",
        "user_name": "chuck"
      },
      {
        "file_uuid": "101/10002/17",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "101/10002/17",
        "project_id": "101",
        "project_name": "biology",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "17",
        "user_id": "12",
        "user_name": "chuck"
      },
      {
        "file_uuid": "105/10001/18",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "105/10001/18",
        "project_id": "105",
        "project_name": "futurology",
        "node_id": "10001",
        "node_name": "beta",
        "file_name": "18",
        "user_id": "12",
        "user_name": "chuck"
      },
      {
        "file_uuid": "105/10003/20",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "105/10003/20",
        "project_id": "105",
        "project_name": "futurology",
        "node_id": "10003",
        "node_name": "delta",
        "file_name": "20",
        "user_id": "12",
        "user_name": "chuck"
      },
      {
        "file_uuid": "101/10000/24",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "101/10000/24",
        "project_id": "101",
        "project_name": "biology",
        "node_id": "10000",
        "node_name": "alpha",
        "file_name": "24",
        "user_id": "12",
        "user_name": "chuck"
      },
      {
        "file_uuid": "100/10001/26",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "100/10001/26",
        "project_id": "100",
        "project_name": "astronomy",
        "node_id": "10001",
        "node_name": "beta",
        "file_name": "26",
        "user_id": "12",
        "user_name": "chuck"
      },
      {
        "file_uuid": "104/10001/28",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "104/10001/28",
        "project_id": "104",
        "project_name": "economics",
        "node_id": "10001",
        "node_name": "beta",
        "file_name": "28",
        "user_id": "12",
        "user_name": "chuck"
      },
      {
        "file_uuid": "104/10002/33",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "104/10002/33",
        "project_id": "104",
        "project_name": "economics",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "33",
        "user_id": "12",
        "user_name": "chuck"
      },
      {
        "file_uuid": "102/10000/38",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "102/10000/38",
        "project_id": "102",
        "project_name": "chemistry",
        "node_id": "10000",
        "node_name": "alpha",
        "file_name": "38",
        "user_id": "12",
        "user_name": "chuck"
      },
      {
        "file_uuid": "106/10002/39",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "106/10002/39",
        "project_id": "106",
        "project_name": "geology",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "39",
        "user_id": "12",
        "user_name": "chuck"
      },
      {
        "file_uuid": "104/10000/46",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "104/10000/46",
        "project_id": "104",
        "project_name": "economics",
        "node_id": "10000",
        "node_name": "alpha",
        "file_name": "46",
        "user_id": "12",
        "user_name": "chuck"
      },
      {
        "file_uuid": "101/10000/50",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "101/10000/50",
        "project_id": "101",
        "project_name": "biology",
        "node_id": "10000",
        "node_name": "alpha",
        "file_name": "50",
        "user_id": "12",
        "user_name": "chuck"
      },
      {
        "file_uuid": "100/10000/52",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "100/10000/52",
        "project_id": "100",
        "project_name": "astronomy",
        "node_id": "10000",
        "node_name": "alpha",
        "file_name": "52",
        "user_id": "12",
        "user_name": "chuck"
      },
      {
        "file_uuid": "102/10001/66",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "102/10001/66",
        "project_id": "102",
        "project_name": "chemistry",
        "node_id": "10001",
        "node_name": "beta",
        "file_name": "66",
        "user_id": "12",
        "user_name": "chuck"
      },
      {
        "file_uuid": "105/10003/68",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "105/10003/68",
        "project_id": "105",
        "project_name": "futurology",
        "node_id": "10003",
        "node_name": "delta",
        "file_name": "68",
        "user_id": "12",
        "user_name": "chuck"
      },
      {
        "file_uuid": "103/10002/80",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "103/10002/80",
        "project_id": "103",
        "project_name": "dermatology",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "80",
        "user_id": "12",
        "user_name": "chuck"
      },
      {
        "file_uuid": "105/10001/82",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "105/10001/82",
        "project_id": "105",
        "project_name": "futurology",
        "node_id": "10001",
        "node_name": "beta",
        "file_name": "82",
        "user_id": "12",
        "user_name": "chuck"
      },
      {
        "file_uuid": "103/10002/87",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "103/10002/87",
        "project_id": "103",
        "project_name": "dermatology",
        "node_id": "10002",
        "node_name": "gamma",
        "file_name": "87",
        "user_id": "12",
        "user_name": "chuck"
      },
      {
        "file_uuid": "106/10001/92",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "106/10001/92",
        "project_id": "106",
        "project_name": "geology",
        "node_id": "10001",
        "node_name": "beta",
        "file_name": "92",
        "user_id": "12",
        "user_name": "chuck"
      },
      {
        "file_uuid": "101/10001/97",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "101/10001/97",
        "project_id": "101",
        "project_name": "biology",
        "node_id": "10001",
        "node_name": "beta",
        "file_name": "97",
        "user_id": "12",
        "user_name": "chuck"
      }, {
        "file_uuid": "one/two/three",
        "location_id": 1,
        "location": "datcore",
        "bucket_name": "",
        "object_name": "",
        "project_id": "",
        "project_name": "",
        "node_id": "",
        "node_name": "",
        "file_name": "",
        "user_id": "",
        "user_name": ""
      }, {
        "file_uuid": "one/two/four",
        "location_id": 1,
        "location": "datcore",
        "bucket_name": "",
        "object_name": "",
        "project_id": "",
        "project_name": "",
        "node_id": "",
        "node_name": "",
        "file_name": "",
        "user_id": "",
        "user_name": ""
      }];
      return objects;
    },



    getItemList: function(nodeInstanceUUID, portKey) {
      switch (portKey) {
        case "defaultNeuromanModels":
          return [{
            key: "Yoon-sun-UUID",
            label: "Yoon-sun",
            thumbnail: "qxapp/yoonsun.png"
          }, {
            key: "Yoon-sun-Light-UUID",
            label: "Yoon-sun Light",
            thumbnail: "qxapp/yoonsun-light.png"
          }, {
            key: "Rat-UUID",
            label: "Rat",
            thumbnail: "qxapp/rat.png"
          }, {
            key: "Rat-Light-UUID",
            label: "Rat Light",
            thumbnail: "qxapp/rat-light.png"
          }];
        case "defaultMaterials":
          return [{
            key: "Dielectric-UUID",
            label: "Dielectric"
          }, {
            key: "PEC-UUID",
            label: "PEC"
          }, {
            key: "PMC-UUID",
            label: "PMC"
          }];
        case "defaultBoundaries":
          return [{
            key: "Dirichlet-UUID",
            label: "Dirichlet"
          }, {
            key: "Neumann-UUID",
            label: "Neumann"
          }, {
            key: "Flux-UUID",
            label: "Flux"
          }];
        case "modeler":
          return [{
            key: "MODEL1-UUID",
            label: "Model 1"
          }, {
            key: "MODEL2-UUID",
            label: "Model 2"
          }, {
            key: "MODEL3-UUID",
            label: "Model 3"
          }];
        case "materialDB":
          return [{
            key: "Air-UUID",
            label: "Air"
          }, {
            key: "Brain-UUID",
            label: "Brain"
          }, {
            key: "Eye-UUID",
            label: "Eye"
          }];
        case "defaultStimulationSelectivity":
          return [{
            key: "StSeSubgroup-UUID",
            label: "Subgroup"
          }];
      }
      return [];
    },

    getItem: function(nodeInstanceUUID, portKey, itemUuid) {
      switch (portKey) {
        case "materialDB": {
          switch (itemUuid) {
            case "Air-UUID": {
              return {
                "massDensity": {
                  displayOrder: 0,
                  label: "Mass Density",
                  unit: "kg/m3",
                  type: "number",
                  defaultValue: 1.16409
                },
                "electricConductivity": {
                  displayOrder: 1,
                  label: "Electric Conductivity",
                  unit: "S/m",
                  type: "number",
                  defaultValue: 0
                },
                "electricRelativePermitivity": {
                  displayOrder: 2,
                  label: "Electric Relative Permittivity",
                  unit: "",
                  type: "number",
                  defaultValue: 1
                },
                "magneticConductivity": {
                  displayOrder: 3,
                  label: "Magnetic Conductivity",
                  unit: "Ohm/m",
                  type: "number",
                  defaultValue: 0
                },
                "magneticRelativePermeability": {
                  displayOrder: 4,
                  label: "Magnetic Relative Permeability",
                  unit: "",
                  type: "number",
                  defaultValue: 1
                }
              };
            }
            case "Brain-UUID": {
              return {
                "massDensity": {
                  displayOrder: 0,
                  label: "Mass Density",
                  unit: "kg/m3",
                  type: "number",
                  defaultValue: 1045.5
                },
                "electricConductivity": {
                  displayOrder: 1,
                  label: "Electric Conductivity",
                  unit: "S/m",
                  type: "number",
                  defaultValue: 0.234007
                },
                "electricRelativePermitivity": {
                  displayOrder: 2,
                  label: "Electric Relative Permittivity",
                  unit: "",
                  type: "number",
                  defaultValue: 1
                },
                "magneticConductivity": {
                  displayOrder: 3,
                  label: "Magnetic Conductivity",
                  unit: "Ohm/m",
                  type: "number",
                  defaultValue: 0
                },
                "magneticRelativePermeability": {
                  displayOrder: 4,
                  label: "Magnetic Relative Permeability",
                  unit: "",
                  type: "number",
                  defaultValue: 1
                }
              };
            }
            case "Eye-UUID": {
              return {
                "massDensity": {
                  displayOrder: 0,
                  label: "Mass Density",
                  unit: "kg/m3",
                  type: "number",
                  defaultValue: 1050.5
                },
                "electricConductivity": {
                  displayOrder: 1,
                  label: "Electric Conductivity",
                  unit: "S/m",
                  type: "number",
                  defaultValue: 0.62
                },
                "electricRelativePermitivity": {
                  displayOrder: 2,
                  label: "Electric Relative Permittivity",
                  unit: "",
                  type: "number",
                  defaultValue: 1
                },
                "magneticConductivity": {
                  displayOrder: 3,
                  label: "Magnetic Conductivity",
                  unit: "Ohm/m",
                  type: "number",
                  defaultValue: 0
                },
                "magneticRelativePermeability": {
                  displayOrder: 4,
                  label: "Magnetic Relative Permeability",
                  unit: "",
                  type: "number",
                  defaultValue: 1
                }
              };
            }
          }
          break;
        }
        case "defaultMaterials": {
          switch (itemUuid) {
            case "Dielectric-UUID": {
              return {
                "massDensity": {
                  displayOrder: 0,
                  label: "Mass Density",
                  unit: "kg/m3",
                  type: "number",
                  defaultValue: 1.205
                },
                "electricConductivity": {
                  displayOrder: 1,
                  label: "Electric Conductivity",
                  unit: "S/m",
                  type: "number",
                  defaultValue: 0
                },
                "electricRelativePermitivity": {
                  displayOrder: 2,
                  label: "Electric Relative Permittivity",
                  unit: "",
                  type: "number",
                  defaultValue: 1
                },
                "magneticRelativePermeability": {
                  displayOrder: 3,
                  label: "Magnetic Relative Permeability",
                  unit: "",
                  type: "number",
                  defaultValue: 1
                },
                "magneticConductivity": {
                  displayOrder: 4,
                  label: "Magnetic Conductivity",
                  unit: "Ohm/m",
                  type: "number",
                  defaultValue: 0
                }
              };
            }
          }
          break;
        }
        case "defaultBoundaries": {
          switch (itemUuid) {
            case "Dirichlet-UUID": {
              return {
                "constantPotential": {
                  displayOrder: 0,
                  label: "Constant Potential",
                  unit: "V",
                  type: "number",
                  defaultValue: 0
                },
                "phase": {
                  displayOrder: 1,
                  label: "Phase",
                  unit: "deg",
                  type: "number",
                  defaultValue: 0
                }
              };
            }
            case "Neumann-UUID": {
              return {
                "normalDerivative": {
                  displayOrder: 0,
                  label: "Normal Derivative",
                  unit: "V/m",
                  type: "number",
                  defaultValue: 0
                },
                "phase": {
                  displayOrder: 1,
                  label: "Phase",
                  unit: "deg",
                  type: "number",
                  defaultValue: 0
                }
              };
            }
            case "Flux-UUID": {
              return {
                "constantFlux": {
                  displayOrder: 0,
                  label: "Constant Flux",
                  type: "number",
                  defaultValue: 0
                },
                "phase": {
                  displayOrder: 1,
                  label: "Phase",
                  unit: "deg",
                  type: "number",
                  defaultValue: 0
                }
              };
            }
          }
          break;
        }
      }
      return {};
    }
  } // statics

});
