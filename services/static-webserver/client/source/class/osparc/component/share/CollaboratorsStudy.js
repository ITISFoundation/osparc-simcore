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

qx.Class.define("osparc.component.share.CollaboratorsStudy", {
  extend: osparc.component.share.Collaborators,

  /**
    * @param studyData {Object} Object containing the serialized Study Data
    */
  construct: function(studyData) {
    // this info is lost when we deepCloneStudyObject
    this.__resourceType = studyData["resourceType"]; // study or template
    const serializedData = osparc.data.model.Study.deepCloneStudyObject(studyData);

    const initCollabs = [];
    if (osparc.data.Permissions.getInstance().canDo("study.everyone.share")) {
      initCollabs.push(this.self().getEveryoneObj(this.__resourceType === "study"));
    }

    this.base(arguments, serializedData, initCollabs);
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

    canGroupsDelete: function(accessRights, gIds) {
      let canWrite = false;
      for (let i=0; i<gIds.length && !canWrite; i++) {
        const gid = gIds[i];
        canWrite = (gid in accessRights) ? accessRights[gid]["delete"] : false;
      }
      return canWrite;
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
        "label": "Public",
        "description": "",
        "thumbnail": null,
        "accessRights": isResourceStudy ? this.getCollaboratorAccessRight() : this.getViewerAccessRight(),
        "collabType": 0
      };
    }
  },

  members: {
    __resourceType: null,

    _canIWrite: function() {
      return osparc.data.model.Study.canIWrite(this._serializedData["accessRights"]);
    },

    _addCollaborators: function(gids, cb) {
      if (gids.length === 0) {
        return;
      }

      gids.forEach(gid => {
        this._serializedData["accessRights"][gid] = this.__resourceType === "study" ? this.self().getCollaboratorAccessRight() : this.self().getViewerAccessRight();
      });
      const params = {
        url: {
          "studyId": this._serializedData["uuid"]
        },
        data: this._serializedData
      };
      osparc.data.Resources.fetch("studies", "put", params)
        .then(updatedData => {
          this.fireDataEvent("updateAccessRights", updatedData);
          const text = this.tr("Collaborator(s) successfully added.");
          osparc.component.message.FlashMessenger.getInstance().logAs(text);
          this._reloadCollaboratorsList();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went adding collaborator(s)"), "ERROR");
          console.error(err);
        })
        .finally(() => cb());

      // push 'study_shared'/'template_shared' notification
      osparc.store.Store.getInstance().getPotentialCollaborators()
        .then(potentialCollaborators => {
          gids.forEach(gid => {
            if (gid in potentialCollaborators && "id" in potentialCollaborators[gid]) {
              // it's a user, not an organization
              const collab = potentialCollaborators[gid];
              const uid = collab["id"];
              if (this.__resourceType === "study") {
                osparc.component.notification.Notifications.postNewStudy(uid, this._serializedData["uuid"]);
              } else {
                osparc.component.notification.Notifications.postNewTemplate(uid, this._serializedData["uuid"]);
              }
            }
          });
        });
    },

    _deleteMember: function(collaborator, item) {
      item.setEnabled(false);
      const success = this.self().removeCollaborator(this._serializedData, collaborator["gid"]);
      if (!success) {
        osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong removing Member"), "ERROR");
        item.setEnabled(true);
      }

      const params = {
        url: {
          "studyId": this._serializedData["uuid"]
        },
        data: this._serializedData
      };
      osparc.data.Resources.fetch("studies", "put", params)
        .then(updatedData => {
          this.fireDataEvent("updateAccessRights", updatedData);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Member successfully removed"));
          this._reloadCollaboratorsList();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong removing Member"), "ERROR");
          console.error(err);
        })
        .finally(() => item.setEnabled(true));
    },

    __make: function(collboratorGId, newAccessRights, successMsg, failureMsg, item) {
      item.setEnabled(false);
      this._serializedData["accessRights"][collboratorGId] = newAccessRights;
      const params = {
        url: {
          "studyId": this._serializedData["uuid"]
        },
        data: this._serializedData
      };
      osparc.data.Resources.fetch("studies", "put", params)
        .then(updatedData => {
          this.fireDataEvent("updateAccessRights", updatedData);
          osparc.component.message.FlashMessenger.getInstance().logAs(successMsg);
          this._reloadCollaboratorsList();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(failureMsg, "ERROR");
          console.error(err);
        })
        .finally(() => item.setEnabled(true));
    },

    _promoteToCollaborator: function(collaborator, item) {
      this.__make(
        collaborator["gid"],
        this.self().getCollaboratorAccessRight(),
        this.tr("Viewer successfully made Collaborator"),
        this.tr("Something went wrong making Viewer Collaborator"),
        item
      );
    },

    _promoteToOwner: function(collaborator, item) {
      this.__make(
        collaborator["gid"],
        this.self().getOwnerAccessRight(),
        this.tr("Collaborator successfully made Owner"),
        this.tr("Something went wrong making Collaborator Owner"),
        item
      );
    },

    _demoteToViewer: function(collaborator, item) {
      this.__make(
        collaborator["gid"],
        this.self().getViewerAccessRight(),
        this.tr("Collaborator successfully made Viewer"),
        this.tr("Something went wrong making Collaborator Viewer"),
        item
      );
    },

    _demoteToCollaborator: function(collaborator, item) {
      this.__make(
        collaborator["gid"],
        this.self().getCollaboratorAccessRight(),
        this.tr("Owner successfully made Collaborator"),
        this.tr("Something went wrong making Owner Collaborator"),
        item
      );
    }
  }
});
