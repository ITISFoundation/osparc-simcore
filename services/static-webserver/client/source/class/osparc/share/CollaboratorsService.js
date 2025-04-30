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
  },

  members: {
    _addEditors: function(gids) {
      if (gids.length === 0) {
        return;
      }

      const readAccessRole = osparc.data.Roles.SERVICES["read"];
      const newAccessRights = this._serializedDataCopy["accessRights"];
      gids.forEach(gid => {
        newAccessRights[gid] = readAccessRole.accessRights;
      });
      osparc.store.Services.patchServiceData(this._serializedDataCopy, "accessRights", newAccessRights)
        .then(() => {
          this.fireDataEvent("updateAccessRights", this._serializedDataCopy);
          const text = this.tr("Service successfully shared");
          osparc.FlashMessenger.logAs(text);
          this._reloadCollaboratorsList();
        })
        .catch(err => osparc.FlashMessenger.logError(err, this.tr("Something went wrong while sharing the service")));
    },

    _deleteMember: function(collaborator, item) {
      if (item) {
        item.setEnabled(false);
      }

      const success = delete this._serializedDataCopy["accessRights"][collaborator["gid"]];
      if (!success) {
        osparc.FlashMessenger.logError(this.tr("Something went wrong while removing member"));
        if (item) {
          item.setEnabled(true);
        }
        return;
      }

      osparc.store.Services.patchServiceData(this._serializedDataCopy, "accessRights", this._serializedDataCopy["accessRights"])
        .then(() => {
          this.fireDataEvent("updateAccessRights", this._serializedDataCopy);
          osparc.FlashMessenger.logAs(collaborator["name"] + this.tr(" successfully removed"));
          this._reloadCollaboratorsList();
        })
        .catch(err => osparc.FlashMessenger.logError(err, this.tr("Something went wrong while removing ") + collaborator["name"]))
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
          osparc.FlashMessenger.logAs(successMsg);
          this._reloadCollaboratorsList();
        })
        .catch(err => osparc.FlashMessenger.logError(err, failureMsg))
        .finally(() => item.setEnabled(true));
    },

    _promoteToEditor: function(collaborator, item) {
      const writeAccessRole = osparc.data.Roles.SERVICES["write"];
      this.__make(
        collaborator["gid"],
        writeAccessRole.accessRights,
        this.tr(`Successfully promoted to ${writeAccessRole.label}`),
        this.tr(`Something went wrong while promoting to ${writeAccessRole.label}`),
        item
      );
    },

    _promoteToOwner: function(collaborator, item) {
      osparc.FlashMessenger.logAs(this.tr("Operation not available"), "WARNING");
    },

    _demoteToUser: function(collaborator, item) {
      const readAccessRole = osparc.data.Roles.SERVICES["read"];
      this.__make(
        collaborator["gid"],
        readAccessRole.accessRights,
        this.tr(`Successfully demoted to ${readAccessRole.label}`),
        this.tr(`Something went wrong while demoting ${readAccessRole.label}`),
        item
      );
    },

    _demoteToEditor: function(collaborator, item) {
      osparc.FlashMessenger.logAs(this.tr("Operation not available"), "WARNING");
    }
  }
});
