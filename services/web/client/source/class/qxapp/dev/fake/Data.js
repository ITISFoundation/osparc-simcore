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
              inputs: {
                inNumber: 3.5
              },
              outputs: {
                outNumber: 33
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

    getUsername: function() {
      return "bizzy";
    },

    getS3PublicBucketName: function() {
      return "simcore";
    },

    getObjectList: function() {
      const objects = [{
        "file_uuid": "simcore.s3/simcore-testing/103/10003/8",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "103/10003/8",
        "project_id": "103",
        "project_name": "dermatology",
        "node_id": "10003",
        "node_name": "delta",
        "file_id": "8",
        "file_name": "8",
        "user_id": "10",
        "user_name": "alice"
      }, {
        "file_uuid": "simcore.s3/simcore-testing/103/10001/11",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "103/10001/11",
        "project_id": "103",
        "project_name": "dermatology",
        "node_id": "10001",
        "node_name": "beta",
        "file_id": "11",
        "file_name": "11",
        "user_id": "10",
        "user_name": "alice"
      }, {
        "file_uuid": "simcore.s3/simcore-testing/102/10001/18",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "102/10001/18",
        "project_id": "102",
        "project_name": "chemistry",
        "node_id": "10001",
        "node_name": "beta",
        "file_id": "18",
        "file_name": "18",
        "user_id": "10",
        "user_name": "alice"
      }, {
        "file_uuid": "simcore.s3/simcore-testing/101/10003/26",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "101/10003/26",
        "project_id": "101",
        "project_name": "biology",
        "node_id": "10003",
        "node_name": "delta",
        "file_id": "26",
        "file_name": "26",
        "user_id": "10",
        "user_name": "alice"
      }, {
        "file_uuid": "simcore.s3/simcore-testing/102/10003/27",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "102/10003/27",
        "project_id": "102",
        "project_name": "chemistry",
        "node_id": "10003",
        "node_name": "delta",
        "file_id": "27",
        "file_name": "27",
        "user_id": "10",
        "user_name": "alice"
      }, {
        "file_uuid": "simcore.s3/simcore-testing/106/10002/29",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "106/10002/29",
        "project_id": "106",
        "project_name": "geology",
        "node_id": "10002",
        "node_name": "gamma",
        "file_id": "29",
        "file_name": "29",
        "user_id": "10",
        "user_name": "alice"
      }, {
        "file_uuid": "simcore.s3/simcore-testing/102/10002/32",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "102/10002/32",
        "project_id": "102",
        "project_name": "chemistry",
        "node_id": "10002",
        "node_name": "gamma",
        "file_id": "32",
        "file_name": "32",
        "user_id": "10",
        "user_name": "alice"
      }, {
        "file_uuid": "simcore.s3/simcore-testing/104/10000/40",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "104/10000/40",
        "project_id": "104",
        "project_name": "economics",
        "node_id": "10000",
        "node_name": "alpha",
        "file_id": "40",
        "file_name": "40",
        "user_id": "10",
        "user_name": "alice"
      }, {
        "file_uuid": "simcore.s3/simcore-testing/101/10002/41",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "101/10002/41",
        "project_id": "101",
        "project_name": "biology",
        "node_id": "10002",
        "node_name": "gamma",
        "file_id": "41",
        "file_name": "41",
        "user_id": "10",
        "user_name": "alice"
      }, {
        "file_uuid": "simcore.s3/simcore-testing/101/10000/51",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "101/10000/51",
        "project_id": "101",
        "project_name": "biology",
        "node_id": "10000",
        "node_name": "alpha",
        "file_id": "51",
        "file_name": "51",
        "user_id": "10",
        "user_name": "alice"
      }, {
        "file_uuid": "simcore.s3/simcore-testing/102/10002/52",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "102/10002/52",
        "project_id": "102",
        "project_name": "chemistry",
        "node_id": "10002",
        "node_name": "gamma",
        "file_id": "52",
        "file_name": "52",
        "user_id": "10",
        "user_name": "alice"
      }, {
        "file_uuid": "simcore.s3/simcore-testing/105/10001/55",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "105/10001/55",
        "project_id": "105",
        "project_name": "futurology",
        "node_id": "10001",
        "node_name": "beta",
        "file_id": "55",
        "file_name": "55",
        "user_id": "10",
        "user_name": "alice"
      }, {
        "file_uuid": "simcore.s3/simcore-testing/106/10001/56",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "106/10001/56",
        "project_id": "106",
        "project_name": "geology",
        "node_id": "10001",
        "node_name": "beta",
        "file_id": "56",
        "file_name": "56",
        "user_id": "10",
        "user_name": "alice"
      }, {
        "file_uuid": "simcore.s3/simcore-testing/106/10001/57",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "106/10001/57",
        "project_id": "106",
        "project_name": "geology",
        "node_id": "10001",
        "node_name": "beta",
        "file_id": "57",
        "file_name": "57",
        "user_id": "10",
        "user_name": "alice"
      }, {
        "file_uuid": "simcore.s3/simcore-testing/103/10001/60",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "103/10001/60",
        "project_id": "103",
        "project_name": "dermatology",
        "node_id": "10001",
        "node_name": "beta",
        "file_id": "60",
        "file_name": "60",
        "user_id": "10",
        "user_name": "alice"
      }, {
        "file_uuid": "simcore.s3/simcore-testing/105/10001/61",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "105/10001/61",
        "project_id": "105",
        "project_name": "futurology",
        "node_id": "10001",
        "node_name": "beta",
        "file_id": "61",
        "file_name": "61",
        "user_id": "10",
        "user_name": "alice"
      }, {
        "file_uuid": "simcore.s3/simcore-testing/102/10002/64",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "102/10002/64",
        "project_id": "102",
        "project_name": "chemistry",
        "node_id": "10002",
        "node_name": "gamma",
        "file_id": "64",
        "file_name": "64",
        "user_id": "10",
        "user_name": "alice"
      }, {
        "file_uuid": "simcore.s3/simcore-testing/100/10002/70",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "100/10002/70",
        "project_id": "100",
        "project_name": "astronomy",
        "node_id": "10002",
        "node_name": "gamma",
        "file_id": "70",
        "file_name": "70",
        "user_id": "10",
        "user_name": "alice"
      }, {
        "file_uuid": "simcore.s3/simcore-testing/104/10002/71",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "104/10002/71",
        "project_id": "104",
        "project_name": "economics",
        "node_id": "10002",
        "node_name": "gamma",
        "file_id": "71",
        "file_name": "71",
        "user_id": "10",
        "user_name": "alice"
      }, {
        "file_uuid": "simcore.s3/simcore-testing/106/10003/72",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "106/10003/72",
        "project_id": "106",
        "project_name": "geology",
        "node_id": "10003",
        "node_name": "delta",
        "file_id": "72",
        "file_name": "72",
        "user_id": "10",
        "user_name": "alice"
      }, {
        "file_uuid": "simcore.s3/simcore-testing/101/10003/76",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "101/10003/76",
        "project_id": "101",
        "project_name": "biology",
        "node_id": "10003",
        "node_name": "delta",
        "file_id": "76",
        "file_name": "76",
        "user_id": "10",
        "user_name": "alice"
      }, {
        "file_uuid": "simcore.s3/simcore-testing/104/10003/79",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "104/10003/79",
        "project_id": "104",
        "project_name": "economics",
        "node_id": "10003",
        "node_name": "delta",
        "file_id": "79",
        "file_name": "79",
        "user_id": "10",
        "user_name": "alice"
      }, {
        "file_uuid": "simcore.s3/simcore-testing/102/10002/86",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "102/10002/86",
        "project_id": "102",
        "project_name": "chemistry",
        "node_id": "10002",
        "node_name": "gamma",
        "file_id": "86",
        "file_name": "86",
        "user_id": "10",
        "user_name": "alice"
      }, {
        "file_uuid": "simcore.s3/simcore-testing/106/10002/95",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "106/10002/95",
        "project_id": "106",
        "project_name": "geology",
        "node_id": "10002",
        "node_name": "gamma",
        "file_id": "95",
        "file_name": "95",
        "user_id": "10",
        "user_name": "alice"
      }, {
        "file_uuid": "simcore.s3/simcore-testing/103/10003/96",
        "location_id": "0",
        "location": "simcore.s3",
        "bucket_name": "simcore-testing",
        "object_name": "103/10003/96",
        "project_id": "103",
        "project_name": "dermatology",
        "node_id": "10003",
        "node_name": "delta",
        "file_id": "96",
        "file_name": "96",
        "user_id": "10",
        "user_name": "alice"
      }, {
        "file_uuid": "simcore/106/10002/95",
        "location": "simcore.sandbox",
        "bucket_name": "simcore",
        "object_name": "106/10002/789",
        "file_name": "789",
        "size": 17224423
      }, {
        "file_uuid": "simcore/103/10003/96",
        "location": "simcore.sandbox",
        "bucket_name": "simcore",
        "object_name": "103/10003/dfgh",
        "file_name": "dfgh",
        "size": 7675509
      }, {
        "file_uuid": "simcore/Large.jpg",
        "location": "simcore.sandbox",
        "bucket_name": "simcore",
        "object_name": "Large.jpg",
        "file_name": "dfgh",
        "size": 342456230
      }];
      return objects;
    },

    getObjectListOld: function() {
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
          projectId: null
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
        projectId: "temp1"
      });
      rawData.push(item1);

      let item2 = qx.data.marshal.Json.createModel({
        name: "Single Cell",
        description: "Colleen Clancy use case",
        thumbnail: null,
        created: null,
        projectId: "temp2"
      });
      rawData.push(item2);

      // A wrapper around raw array to make it "bindable"
      var data = new qx.data.Array(rawData);
      return data;
    },

    getPrjData: function(projectId) {
      switch (projectId) {
        case "temp2": {
          let tempData = this.getTemp2Data();
          return tempData;
        }
      }
      return null;
    },

    getTemp2Data: function() {
      let temp2Data = {
        name: "Colleen Clancy template",
        description: "Template for the Colleen Clancy template",
        notes: "# title\nSingle Cell",
        owner: "CC",
        collaborators: {
          "PEDRO": [
            "read",
            "write"
          ]
        },
        creationDate: "2018-07-02T16:01:00Z",
        lastChangeDate: "2018-07-02T16:02:22Z",
        workbench: {
          "UUID5": {
            key: "services/dynamic/itis/file-picker",
            version: "0.0.0",
            inputs: {},
            outputs: {
              outFile: {
                store: "s3-z43",
                path: "/bucket1/file1"
              },
              outDir: null
            },
            position: {
              x: 50,
              y: 100
            }
          },
          "UUID6": {
            key: "simcore/services/comp/ucdavis/cardiac-singlecell",
            version: "0.0.1",
            inputs: {
              Na: 0.0,
              Kr: 0.0,
              BCL: 200,
              NBeats: 5,
              Ligand: 0.0,
              cAMKII: 0.0,
              "initial_WTstates.txt": {
                nodeUuid: "UUID5",
                output: "outFile"
              },
              "initial_WTstates2.txt": {
                nodeUuid: "UUID5",
                output: "outFile"
              }
            },
            outputs: {
              "Allresult_1Hz.txt": null,
              "apds_1Hz.txt": null,
              "finalStates.txt": null,
              "vm_1Hz.txt": null
            },
            inputNodes: [
              "UUID5"
            ],
            position: {
              x: 350,
              y: 100
            }
          },
          "UUID7": {
            key: "simcore/services/dynamic/cc-0d-viewer",
            version: "1.0",
            inputs: {
              "in_1": {
                nodeUuid: "UUID6",
                output: "vm_1Hz.txt"
              },
              "in_2": {
                nodeUuid: "UUID6",
                output: "Allresult_1Hz.txt"
              }
            },
            outputs: {},
            inputNodes: [
              "UUID6"
            ],
            position: {
              x: 700,
              y: 100
            }
          }
        }
      };
      return temp2Data;
    }
  } // statics

});
