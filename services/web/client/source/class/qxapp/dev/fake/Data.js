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
        "service/dynamic/itis/file-picker-0.0.0":{
          key: "service/dynamic/itis/file-picker",
          version: "0.0.0",
          type: "dynamic",
          name: "filepicker service",
          description: "dummy file picker",
          authors: [
            {
              name: "Odei Maiz",
              email: "maiz@itis.ethz.ch"
            }
          ],
          contact: "maiz@itis.ethz.ch",
          inputs: {},
          outputs: {
            outFile: {
              displayOrder: 0,
              label: "File",
              description: "Chosen File",
              type: "data:*/*"
            }
          }
        },
        "service/computational/itis/sleeper-0.0.0":{
          key: "service/computational/itis/sleeper",
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
        "service/computational/itis/tutti-0.0.0-alpha": {
          key: "service/computational/itis/tutti",
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

    getProjectList: function() {
      return [
        {
          name: "Sample Project",
          description: "A little fake project without actual backend",
          notes: "# title\nThere be dragons inside",
          owner: "UUID-OF-TOBI",
          collaborators: {
            "UUID-OF-PEDRO": [
              "read",
              "write"
            ]
          },
          creationDate: "2018-07-02T16:01:00Z",
          lastChangeDate: "2018-07-02T16:02:22Z",
          workbench: {
            "UUID1": {
              key: "service/dynamic/itis/file-picker",
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
              key: "service/computational/itis/sleeper",
              version: "0.0.0",
              inputs: {
                inNumber: 3.5
              },
              outputs: {
                outNumber: 33
              },
              position: {
                x: 300,
                y: 10
              }
            },
            "UUID3": {
              key: "service/computational/itis/sleeper",
              version: "0.0.0",
              inputs: {
                inNumber: 3.5
              },
              outputs: {
                outNumber: 33
              },
              position: {
                x: 10,
                y: 210
              }
            },
            "UUID4": {
              key: "service/computational/itis/tutti",
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
                  store: "s3-z43",
                  path: "bucket33/file.data"
                },
                inImage: {
                  store: "s3-z43",
                  path: "bucket32/file.png"
                }
              },
              position: {
                x: 300,
                y: 210
              }
            }
          }
        },
        {
          name: "Sample Project II",
          description: "An empty project",
          notes: "# title\nThere be dragons inside",
          owner: "UUID-OF-TOBI",
          collaborators: {
            "UUID-OF-PEDRO": [
              "read",
              "write"
            ]
          },
          creationDate: "2018-07-08T16:01:00Z",
          lastChangeDate: "2018-07-09T16:02:22Z",
          workbench: {}
        }
      ];
    },

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
        owner: "UUID-OF-CC",
        collaborators: {
          "UUID-OF-PEDRO": [
            "read",
            "write"
          ]
        },
        creationDate: "2018-07-02T16:01:00Z",
        lastChangeDate: "2018-07-02T16:02:22Z",
        workbench: {
          "UUID5": {
            key: "service/dynamic/itis/file-picker",
            version: "0.0.0",
            inputs: {},
            outputs: {
              outFile: {
                store: "s3-z43",
                path: "/bucket1/file1"
              }
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
              }
            },
            outputs: {
              "Allresult_1Hz.txt": null,
              "apds_1Hz.txt": null,
              "finalStates.txt": null,
              "vm_1Hz.txt": null
            },
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
