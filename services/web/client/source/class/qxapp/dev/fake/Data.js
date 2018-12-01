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
        "simcore/services/computational/itis/sleeper-0.0.0":{
          key: "simcore/services/computational/itis/sleeper",
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
        "simcore/services/computational/itis/tutti-0.0.0-alpha": {
          key: "simcore/services/computational/itis/tutti",
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


    getItemList: function(nodeKey, portKey) {
      switch (portKey) {
        case "defaultNeuromanModels":
          return qxapp.dev.fake.neuroman.Data.getItemList(portKey);
        case "modeler":
          return qxapp.dev.fake.modeler.Data.getItemList();
        case "materialDB":
          return qxapp.dev.fake.materialDB.Data.getItemList();
        case "defaultLFMaterials":
        case "defaultLFBoundaries":
        case "defaultLFSensors":
        case "sensorSettingAPI":
          return qxapp.dev.fake.lf.Data.getItemList(portKey);
        case "defaultNeurons":
        case "defaultNeuronSources":
        case "defaultNeuronPointProcesses":
        case "defaultNeuronNetworkConnection":
        case "defaultNeuronSensors":
        case "neuronsSetting":
          return qxapp.dev.fake.neuron.Data.getItemList(portKey);
        case "defaultStimulationSelectivity":
          return qxapp.dev.fake.stimulationSelectivity.Data.getItemList();
      }
      return [];
    },

    getItem: function(nodeInstanceUUID, portKey, itemUuid) {
      switch (portKey) {
        case "materialDB":
          return qxapp.dev.fake.materialDB.Data.getItem(itemUuid);
        case "defaultLFMaterials":
        case "defaultLFBoundaries":
        case "defaultLFSensors":
          return qxapp.dev.fake.lf.Data.getItem(portKey, itemUuid);
        case "defaultNeurons":
        case "defaultNeuronSources":
        case "defaultNeuronPointProcesses":
        case "defaultNeuronNetworkConnection":
        case "defaultNeuronSensors":
          return qxapp.dev.fake.neuron.Data.getItem(portKey, itemUuid);
      }
      return {};
    }
  } // statics

});
