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

qx.Class.define("osparc.component.permissions.PermissionsStudy", {
  extend: osparc.component.permissions.Permissions,

  /**
    * @param studyData {Object} Object containing the serialized Study Data
    */
  construct: function(studyData) {
    this.__studyData = osparc.data.model.Study.deepCloneStudyObject(studyData);

    this.base(arguments, this.__studyData);
  },

  events: {
    "updateStudy": "qx.event.type.Data"
  },

  statics: {
    canGroupRead: function(accessRights, GID) {
      if (GID in accessRights) {
        return accessRights[GID]["read"];
      }
      return false;
    },
    canGroupWrite: function(accessRights, GID) {
      if (GID in accessRights) {
        return accessRights[GID]["write"];
      }
      return false;
    },
    canGroupExecute: function(accessRights, GID) {
      if (GID in accessRights) {
        return accessRights[GID]["delete"];
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
    }
  },

  members: {
    __studyData: null,

    _isUserOwner: function() {
      return osparc.data.model.Study.isOwner(this.__studyData);
    },

    _addCollaborator: function() {
      const gids = this.__organizationsAndMembers.getSelectedGIDs();
      if (gids.length === 0) {
        return;
      }

      gids.forEach(gid => {
        this.__studyData["accessRights"][gid] = this.self().getCollaboratorAccessRight();
      });
      const params = {
        url: {
          "projectId": this.__studyData["uuid"]
        },
        data: this.__studyData
      };
      osparc.data.Resources.fetch("studies", "put", params)
        .then(() => {
          this.fireDataEvent("updateStudy", this.__studyData["uuid"]);
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
          "projectId": this.__studyData["uuid"]
        },
        data: this.__studyData
      };
      osparc.data.Resources.fetch("studies", "put", params)
        .then(() => {
          this.fireDataEvent("updateStudy", this.__studyData["uuid"]);
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
          "projectId": this.__studyData["uuid"]
        },
        data: this.__studyData
      };
      osparc.data.Resources.fetch("studies", "put", params)
        .then(() => {
          this.fireDataEvent("updateStudy", this.__studyData["uuid"]);
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
