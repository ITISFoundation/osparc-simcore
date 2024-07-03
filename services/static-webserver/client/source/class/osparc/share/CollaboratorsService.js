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

    osparc.data.Roles.createServicesRolesResourceInfo();

    const initCollabs = [];
    initCollabs.push(this.self().getEveryoneProductObj());
    initCollabs.push(this.self().getEveryoneObj());

    this.base(arguments, serviceDataCopy, initCollabs);
  },

  events: {
    "updateAccessRights": "qx.event.type.Data"
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

    getEveryoneProductObj: function() {
      const everyoneProductGroup = osparc.store.Store.getInstance().getEveryoneProductGroup();
      const everyone = osparc.utils.Utils.deepCloneObject(everyoneProductGroup);
      everyone["accessRights"] = this.getCollaboratorAccessRight();
      return everyone;
    },

    getEveryoneObj: function() {
      const everyoneGroup = osparc.store.Store.getInstance().getEveryoneGroup();
      const everyone = osparc.utils.Utils.deepCloneObject(everyoneGroup);
      everyone["accessRights"] = this.getCollaboratorAccessRight();
      return everyone;
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

      const newAccessRights = this._serializedDataCopy["accessRights"];
      gids.forEach(gid => {
        newAccessRights[gid] = this.self().getCollaboratorAccessRight();
      });
      osparc.info.ServiceUtils.patchServiceData(this._serializedDataCopy, "accessRights", newAccessRights)
        .then(() => {
          this.fireDataEvent("updateAccessRights", this._serializedDataCopy);
          let text = this.tr("Editor(s) successfully added.");
          text += "<br>";
          text += this.tr("The user will not get notified.");
          osparc.FlashMessenger.getInstance().logAs(text);
          this._reloadCollaboratorsList();
        })
        .catch(err => {
          console.error(err);
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong adding editor(s)"), "ERROR");
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
        return;
      }

      osparc.info.ServiceUtils.patchServiceData(this._serializedDataCopy, "accessRights", this._serializedDataCopy["accessRights"])
        .then(() => {
          this.fireDataEvent("updateAccessRights", this._serializedDataCopy);
          osparc.FlashMessenger.getInstance().logAs(this.tr("Member successfully removed"));
          this._reloadCollaboratorsList();
        })
        .catch(err => {
          console.error(err);
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong removing Member"), "ERROR");
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
      osparc.info.ServiceUtils.patchServiceData(this._serializedDataCopy, "accessRights", this._serializedDataCopy["accessRights"])
        .then(() => {
          this.fireDataEvent("updateAccessRights", this._serializedDataCopy);
          osparc.FlashMessenger.getInstance().logAs(successMsg);
          this._reloadCollaboratorsList();
        })
        .catch(err => {
          console.error(err);
          osparc.FlashMessenger.getInstance().logAs(failureMsg, "ERROR");
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
