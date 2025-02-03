/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.store.Study", {
  type: "static",

  statics: {
    patchStudyData: function(studyData, fieldKey, value) {
      if (osparc.data.model.Study.OwnPatch.includes(fieldKey)) {
        console.error(fieldKey, "has it's own PATCH path");
        return null;
      }

      const patchData = {};
      patchData[fieldKey] = value;
      const params = {
        url: {
          "studyId": studyData["uuid"]
        },
        data: patchData
      };
      return osparc.data.Resources.fetch("studies", "patch", params)
        .then(() => {
          studyData[fieldKey] = value;
          // A bit hacky, but it's not sent back to the backend
          studyData["lastChangeDate"] = new Date().toISOString();
        });
    },

    patchNodeData: function(studyData, nodeId, patchData) {
      const params = {
        url: {
          "studyId": studyData["uuid"],
          "nodeId": nodeId
        },
        data: patchData
      };
      return osparc.data.Resources.fetch("studies", "patchNode", params)
        .then(() => {
          Object.keys(patchData).forEach(key => {
            studyData["workbench"][nodeId][key] = patchData[key];
          });
          // A bit hacky, but it's not sent back to the backend
          studyData["lastChangeDate"] = new Date().toISOString();
        });
    },

    addCollaborators: function(studyData, newCollaborators) {
      const promises = [];
      Object.keys(newCollaborators).forEach(gid => {
        const params = {
          url: {
            "studyId": studyData["uuid"],
            "gId": gid
          },
          data: newCollaborators[gid]
        };
        promises.push(osparc.data.Resources.fetch("studies", "postAccessRights", params));
      });
      return Promise.all(promises)
        .then(() => {
          Object.keys(newCollaborators).forEach(gid => {
            studyData["accessRights"][gid] = newCollaborators[gid];
          });
          studyData["lastChangeDate"] = new Date().toISOString();
        })
        .catch(err => osparc.FlashMessenger.logAs(err.message, "ERROR"));
    },

    removeCollaborator: function(studyData, gid) {
      const params = {
        url: {
          "studyId": studyData["uuid"],
          "gId": gid
        }
      };
      return osparc.data.Resources.fetch("studies", "deleteAccessRights", params)
        .then(() => {
          delete studyData["accessRights"][gid];
          studyData["lastChangeDate"] = new Date().toISOString();
        })
        .catch(err => osparc.FlashMessenger.logAs(err.message, "ERROR"));
    },

    updateCollaborator: function(studyData, gid, newPermissions) {
      const params = {
        url: {
          "studyId": studyData["uuid"],
          "gId": gid
        },
        data: newPermissions
      };
      return osparc.data.Resources.fetch("studies", "putAccessRights", params)
        .then(() => {
          studyData["accessRights"][gid] = newPermissions;
          studyData["lastChangeDate"] = new Date().toISOString();
        })
        .catch(err => osparc.FlashMessenger.logAs(err.message, "ERROR"));
    },
  }
});
