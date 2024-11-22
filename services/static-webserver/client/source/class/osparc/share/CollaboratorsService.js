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

    this.base(arguments, serviceDataCopy);
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

    getCollaboratorAccessRight: function() {
      return {
        "execute": true,
        "write": false
      };
    },

    getOwnerAccessRight: function() {
      return {
        "execute": true,
        "write": true
      };
    },
  },

  members: {
    _addEditors: function(gids) {
      if (gids.length === 0) {
        return;
      }

      const newAccessRights = this._serializedDataCopy["accessRights"];
      gids.forEach(gid => {
        newAccessRights[gid] = this.self().getCollaboratorAccessRight();
      });
      osparc.store.Services.patchServiceData(this._serializedDataCopy, "accessRights", newAccessRights)
        .then(() => {
          this.fireDataEvent("updateAccessRights", this._serializedDataCopy);
          const text = this.tr("Service successfully shared");
          osparc.FlashMessenger.getInstance().logAs(text);
          this._reloadCollaboratorsList();
        })
        .catch(err => {
          console.error(err);
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong sharing the Service"), "ERROR");
        });
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

      osparc.store.Services.patchServiceData(this._serializedDataCopy, "accessRights", this._serializedDataCopy["accessRights"])
        .then(() => {
          this.fireDataEvent("updateAccessRights", this._serializedDataCopy);
          osparc.FlashMessenger.getInstance().logAs(collaborator["name"] + this.tr(" successfully removed"));
          this._reloadCollaboratorsList();
        })
        .catch(err => {
          console.error(err);
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong removing ") + collaborator["name"], "ERROR");
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
      osparc.store.Services.patchServiceData(this._serializedDataCopy, "accessRights", this._serializedDataCopy["accessRights"])
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
        this.tr(`Successfully promoted to ${osparc.data.Roles.SERVICE[2].label}`),
        this.tr(`Something went wrong promoting to ${osparc.data.Roles.SERVICE[2].label}`),
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
        this.tr(`Successfully demoted to ${osparc.data.Roles.SERVICE[1].label}`),
        this.tr(`Something went wrong demoting ${osparc.data.Roles.SERVICE[1].label}`),
        item
      );
    },

    _demoteToEditor: function(collaborator, item) {
      osparc.FlashMessenger.getInstance().logAs(this.tr("Operation not available"), "WARNING");
    }
  }
});
