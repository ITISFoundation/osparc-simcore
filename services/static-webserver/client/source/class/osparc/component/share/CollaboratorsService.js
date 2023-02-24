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
 * Widget for modifying Service permissions. This is the way for sharing studies
 * - Creates a copy of service data
 * - It allows changing study's access right, so that the study owners can:
 *   - Share it with Organizations and/or Organization Members (Collaborators)
 *   - Make other Collaborators Owner
 *   - Remove Collaborators
 */

qx.Class.define("osparc.component.share.CollaboratorsService", {
  extend: osparc.component.share.Collaborators,

  /**
    * @param serviceData {Object} Object containing the Service Data
    */
  construct: function(serviceData) {
    const serializedData = osparc.utils.Utils.deepCloneObject(serviceData);

    const initCollabs = this.self().getEveryoneObj();

    this.base(arguments, serializedData, [initCollabs]);
  },

  events: {
    "updateService": "qx.event.type.Data"
  },

  statics: {
    canGroupsWrite: function(accessRights, gIds) {
      let canWrite = false;
      for (let i=0; i<gIds.length && !canWrite; i++) {
        const gid = gIds[i];
        canWrite = (gid in accessRights) ? accessRights[gid]["write_access"] : false;
      }
      return canWrite;
    },

    getCollaboratorAccessRight: function() {
      return {
        "execute_access": true,
        "write_access": false
      };
    },

    getOwnerAccessRight: function() {
      return {
        "execute_access": true,
        "write_access": true
      };
    },

    removeCollaborator: function(serializedData, gid) {
      return delete serializedData["accessRights"][gid];
    },

    getEveryoneObj: function() {
      return {
        "gid": 1,
        "label": "Public",
        "description": "",
        "thumbnail": null,
        "accessRights": this.getCollaboratorAccessRight(),
        "collabType": 0
      };
    }
  },

  members: {
    _canIWrite: function() {
      return osparc.utils.Services.canIWrite(this._serializedData["accessRights"]);
    },

    _addCollaborators: function(gids, cb) {
      if (gids.length === 0) {
        return;
      }
      gids.forEach(gid => {
        this._serializedData["accessRights"][gid] = this.self().getCollaboratorAccessRight();
      });
      const params = {
        url: osparc.data.Resources.getServiceUrl(
          this._serializedData["key"],
          this._serializedData["version"]
        ),
        data: this._serializedData
      };
      osparc.data.Resources.fetch("services", "patch", params)
        .then(serviceData => {
          this.fireDataEvent("updateService", serviceData);
          let text = this.tr("Collaborator(s) successfully added.");
          text += "<br>";
          text += this.tr("The user will not get notified.");
          osparc.component.message.FlashMessenger.getInstance().logAs(text);
          this._reloadCollaboratorsList();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went adding collaborator(s)"), "ERROR");
          console.error(err);
        })
        .finally(() => cb());
    },

    _deleteMember: function(collaborator, item) {
      const success = this.self().removeCollaborator(this._serializedData, collaborator["gid"]);
      if (!success) {
        osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong removing Member"), "ERROR");
      }

      const params = {
        url: osparc.data.Resources.getServiceUrl(
          this._serializedData["key"],
          this._serializedData["version"]
        ),
        data: this._serializedData
      };
      osparc.data.Resources.fetch("services", "patch", params)
        .then(serviceData => {
          this.fireDataEvent("updateService", serviceData);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Member successfully removed"));
          this._reloadCollaboratorsList();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong removing Member"), "ERROR");
          console.error(err);
        });
    },

    __make: function(collboratorGId, newAccessRights, successMsg, failureMsg, item) {
      item.setEnabled(false);
      this._serializedData["accessRights"][collboratorGId] = newAccessRights;
      const params = {
        url: osparc.data.Resources.getServiceUrl(
          this._serializedData["key"],
          this._serializedData["version"]
        ),
        data: this._serializedData
      };
      osparc.data.Resources.fetch("services", "patch", params)
        .then(serviceData => {
          this.fireDataEvent("updateService", serviceData);
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
        this.self().getOwnerAccessRight(),
        this.tr("Viewer successfully made Collaborator"),
        this.tr("Something went wrong making Viewer Collaborator"),
        item
      );
    },

    _promoteToOwner: function(collaborator, item) {
      osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Operation not available"), "WARNING");
    },

    _demoteToViewer: function(collaborator, item) {
      this.__make(
        collaborator["gid"],
        this.self().getCollaboratorAccessRight(),
        this.tr("Collaborator successfully made Viewer"),
        this.tr("Something went wrong making Collaborator Viewer"),
        item
      );
    },

    _demoteToCollaborator: function(collaborator, item) {
      osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Operation not available"), "WARNING");
    }
  }
});
