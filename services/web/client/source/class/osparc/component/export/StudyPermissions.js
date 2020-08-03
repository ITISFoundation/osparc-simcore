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

qx.Class.define("osparc.component.export.StudyPermissions", {
  extend: osparc.component.export.Permissions,

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

  members: {
    __studyData: null,

    _isUserOwner: function() {
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      const aceessRights = this.__studyData["accessRights"];
      if (myGid in aceessRights) {
        return aceessRights[myGid]["delete"];
      }
      return false;
    },

    _addCollaborator: function() {
      const gids = this.__organizationsAndMembers.getSelectedGIDs();
      if (gids.length === 0) {
        return;
      }

      gids.forEach(gid => {
        this.__studyData["accessRights"][gid] = osparc.component.export.Permissions.getCollaboratorAccessRight();
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

    _promoteCollaborator: function(collaborator) {
      this.__studyData["accessRights"][collaborator["gid"]] = osparc.component.export.Permissions.getOwnerAccessRight();
      const params = {
        url: {
          "projectId": this.__studyData["uuid"]
        },
        data: this.__studyData
      };
      osparc.data.Resources.fetch("studies", "put", params)
        .then(() => {
          this.fireDataEvent("updateStudy", this.__studyData["uuid"]);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Collaborator successfully made Owner"));
          this.__reloadOrganizationsAndMembers();
          this.__reloadCollaboratorsList();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong making Collaborator Owner"), "ERROR");
          console.error(err);
        });
    },

    _deleteCollaborator: function(collaborator) {
      const success = osparc.component.export.Permissions.removeCollaborator(this.__studyData, collaborator["gid"]);
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
    }
  }
});
