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
 *   - Share it with Organizations and/or Organization Members (Editors)
 *   - Make other Editors Owner
 *   - Remove Editors
 */

qx.Class.define("osparc.share.CollaboratorsService", {
  extend: osparc.share.Collaborators,

  /**
    * @param serviceData {Object} Object containing the Service Data
    */
  construct: function(serviceData) {
    this._resourceType = "service";
    const serviceDataCopy = osparc.utils.Utils.deepCloneObject(serviceData);

    if (serviceData.resourceType === "service") {
      osparc.data.Roles.createServicesRolesResourceInfo();
    }

    const initCollabs = this.self().getEveryoneObj();

    this.base(arguments, serviceDataCopy, [initCollabs]);
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
      return osparc.service.Utils.canIWrite(this._serializedDataCopy["accessRights"]);
    },

    _addEditors: function(gids, cb) {
      if (gids.length === 0) {
        return;
      }
      gids.forEach(gid => {
        this._serializedDataCopy["accessRights"][gid] = this.self().getCollaboratorAccessRight();
      });
      const params = {
        url: osparc.data.Resources.getServiceUrl(
          this._serializedDataCopy["key"],
          this._serializedDataCopy["version"]
        ),
        data: this._serializedDataCopy
      };
      osparc.data.Resources.fetch("services", "patch", params)
        .then(serviceData => {
          this.fireDataEvent("updateService", serviceData);
          let text = this.tr("Editor(s) successfully added.");
          text += "<br>";
          text += this.tr("The user will not get notified.");
          osparc.FlashMessenger.getInstance().logAs(text);
          this._reloadCollaboratorsList();
        })
        .catch(err => {
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went adding editor(s)"), "ERROR");
          console.error(err);
        })
        .finally(() => cb());
    },

    _deleteMember: function(collaborator, item) {
      if (item) {
        item.setEnabled(false);
      }

      const success = delete this._serializedDataCopy["accessRights"][collaborator["gid"]];
      if (!success) {
        osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong removing Member"), "ERROR");
        if (item) {
          item.setEnabled(true);
        }
      }

      const params = {
        url: osparc.data.Resources.getServiceUrl(
          this._serializedDataCopy["key"],
          this._serializedDataCopy["version"]
        ),
        data: this._serializedDataCopy
      };
      osparc.data.Resources.fetch("services", "patch", params)
        .then(serviceData => {
          this.fireDataEvent("updateService", serviceData);
          osparc.FlashMessenger.getInstance().logAs(this.tr("Member successfully removed"));
          this._reloadCollaboratorsList();
        })
        .catch(err => {
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong removing Member"), "ERROR");
          console.error(err);
        })
        .finally(() => {
          if (item) {
            item.setEnabled(true);
          }
        });
    },

    __make: function(collaboratorGId, newAccessRights, successMsg, failureMsg, item) {
      item.setEnabled(false);
      this._serializedDataCopy["accessRights"][collaboratorGId] = newAccessRights;
      const params = {
        url: osparc.data.Resources.getServiceUrl(
          this._serializedDataCopy["key"],
          this._serializedDataCopy["version"]
        ),
        data: this._serializedDataCopy
      };
      osparc.data.Resources.fetch("services", "patch", params)
        .then(serviceData => {
          this.fireDataEvent("updateService", serviceData);
          osparc.FlashMessenger.getInstance().logAs(successMsg);
          this._reloadCollaboratorsList();
        })
        .catch(err => {
          osparc.FlashMessenger.getInstance().logAs(failureMsg, "ERROR");
          console.error(err);
        })
        .finally(() => item.setEnabled(true));
    },

    _promoteToEditor: function(collaborator, item) {
      this.__make(
        collaborator["gid"],
        this.self().getOwnerAccessRight(),
        this.tr("Viewer successfully made Editor"),
        this.tr("Something went wrong making Viewer Editor"),
        item
      );
    },

    _promoteToOwner: function(collaborator, item) {
      osparc.FlashMessenger.getInstance().logAs(this.tr("Operation not available"), "WARNING");
    },

    _demoteToUser: function(collaborator, item) {
      this.__make(
        collaborator["gid"],
        this.self().getCollaboratorAccessRight(),
        this.tr("Editor successfully made Viewer"),
        this.tr("Something went wrong making Editor Viewer"),
        item
      );
    },

    _demoteToEditor: function(collaborator, item) {
      osparc.FlashMessenger.getInstance().logAs(this.tr("Operation not available"), "WARNING");
    }
  }
});
