/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget for modifying Study permissions. This is the way for sharing studies
 * - Creates a copy of study data
 * - It allows changing study's access right, so that the study owners can:
 *   - Share it with Organizations and/or Organization Members (Collaborators)
 *   - Make other Collaborators Owner
 *   - Remove collaborators
 */

qx.Class.define("osparc.component.permissions.Study", {
  extend: osparc.component.permissions.Permissions,

  /**
    * @param studyData {Object} Object containing the serialized Study Data
    */
  construct: function(studyData) {
    // this info is lost when we deepCloneStudyObject
    this.__resourceType = studyData["resourceType"];
    this.__studyData = osparc.data.model.Study.deepCloneStudyObject(studyData);

    const initCollabs = [];
    if (osparc.data.Permissions.getInstance().canDo("study.everyone.share")) {
      initCollabs.push(this.self().getEveryoneObj(this.__resourceType === "study"));
    }
    this.base(arguments, this.__studyData, initCollabs);
  },

  events: {
    "updateAccessRights": "qx.event.type.Data"
  },

  statics: {
    canGroupsWrite: function(accessRights, gIds) {
      let canWrite = false;
      for (let i=0; i<gIds.length && !canWrite; i++) {
        const gid = gIds[i];
        canWrite = (gid in accessRights) ? accessRights[gid]["write"] : false;
      }
      return canWrite;
    },

    canGroupDelete: function(accessRights, gid) {
      if (gid in accessRights) {
        return accessRights[gid]["delete"];
      }
      return false;
    },

    getViewerAccessRight: function() {
      return {
        "read": true,
        "write": false,
        "delete": false
      };
    },

    getCollaboratorAccessRight: function() {
      return {
        "read": true,
        "write": true,
        "delete": false
      };
    },

    getOwnerAccessRight: function() {
      return {
        "read": true,
        "write": true,
        "delete": true
      };
    },

    removeCollaborator: function(studyData, gid) {
      return delete studyData["accessRights"][gid];
    },

    getEveryoneObj: function(isResourceStudy) {
      return {
        "gid": 1,
        "label": "Everyone",
        "description": "",
        "thumbnail": null,
        "accessRights": isResourceStudy ? this.getCollaboratorAccessRight() : this.getViewerAccessRight(),
        "collabType": 0
      };
    }
  },

  members: {
    __studyData: null,
    __resourceType: null,

    _isUserOwner: function() {
      return osparc.data.model.Study.isOwner(this.__studyData);
    },

    _addCollaborator: function() {
      const gids = this.__organizationsAndMembers.getSelectedGIDs();
      if (gids.length === 0) {
        return;
      }

      gids.forEach(gid => {
        this.__studyData["accessRights"][gid] = this.__resourceType === "study" ? this.self().getCollaboratorAccessRight() : this.self().getViewerAccessRight();
      });
      const params = {
        url: {
          "studyId": this.__studyData["uuid"]
        },
        data: this.__studyData
      };
      osparc.data.Resources.fetch("studies", "put", params)
        .then(updatedData => {
          this.fireDataEvent("updateAccessRights", updatedData);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Collaborator(s) successfully added"));
          this.__reloadOrganizationsAndMembers();
          this.__reloadCollaboratorsList();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went adding collaborator(s)"), "ERROR");
          console.error(err);
        });
    },

    _deleteCollaborator: function(collaborator) {
      const success = this.self().removeCollaborator(this.__studyData, collaborator["gid"]);
      if (!success) {
        osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong removing Collaborator"), "ERROR");
      }

      const params = {
        url: {
          "studyId": this.__studyData["uuid"]
        },
        data: this.__studyData
      };
      osparc.data.Resources.fetch("studies", "put", params)
        .then(updatedData => {
          this.fireDataEvent("updateAccessRights", updatedData);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Collaborator successfully removed"));
          this.__reloadOrganizationsAndMembers();
          this.__reloadCollaboratorsList();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong removing Collaborator"), "ERROR");
          console.error(err);
        });
    },

    __make: function(collboratorGId, newAccessRights, successMsg, failureMsg) {
      this.__studyData["accessRights"][collboratorGId] = newAccessRights;
      const params = {
        url: {
          "studyId": this.__studyData["uuid"]
        },
        data: this.__studyData
      };
      osparc.data.Resources.fetch("studies", "put", params)
        .then(updatedData => {
          this.fireDataEvent("updateAccessRights", updatedData);
          osparc.component.message.FlashMessenger.getInstance().logAs(successMsg);
          this.__reloadOrganizationsAndMembers();
          this.__reloadCollaboratorsList();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(failureMsg, "ERROR");
          console.error(err);
        });
    },

    _makeOwner: function(collaborator) {
      this.__make(
        collaborator["gid"],
        this.self().getOwnerAccessRight(),
        this.tr("Collaborator successfully made Owner"),
        this.tr("Something went wrong making Collaborator Owner")
      );
    },

    _makeCollaborator: function(collaborator) {
      this.__make(
        collaborator["gid"],
        this.self().getCollaboratorAccessRight(),
        this.tr("Viewer successfully made Collaborator"),
        this.tr("Something went wrong making Viewer Collaborator")
      );
    },

    _makeViewer: function(collaborator) {
      this.__make(
        collaborator["gid"],
        this.self().getViewerAccessRight(),
        this.tr("Collaborator successfully made Viewer"),
        this.tr("Something went wrong making Collaborator Viewer")
      );
    }
  }
});
