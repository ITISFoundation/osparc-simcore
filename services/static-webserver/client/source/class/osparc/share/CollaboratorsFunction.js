/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.share.CollaboratorsFunction", {
  extend: osparc.share.Collaborators,

  /**
    * @param functionData {Object} Object containing the serialized function Data
    */
  construct: function(functionData) {
    this._resourceType = "function";
    const functionDataCopy = osparc.utils.Utils.deepCloneObject(functionData);

    this.base(arguments, functionDataCopy);
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
    _addEditors: function(gids, newAccessRights) {
      if (gids.length === 0) {
        return;
      }

      if (!newAccessRights) {
        // default access rights
        const readAccessRole = osparc.data.Roles.FUNCTION["read"];
        newAccessRights = readAccessRole.accessRights;
      }

      const resourceAlias = osparc.product.Utils.resourceTypeToAlias(this._resourceType, {firstUpperCase: true});
      const newCollaborators = {};
      gids.forEach(gid => {
        newCollaborators[gid] = newAccessRights;
      });
      osparc.store.Functions.addCollaborators(this._serializedDataCopy, newCollaborators)
        .then(() => {
          const text = resourceAlias + this.tr(" successfully shared");
          osparc.FlashMessenger.logAs(text);
          this.fireDataEvent("updateAccessRights", this._serializedDataCopy);
          this._reloadCollaboratorsList();
        })
        .catch(err => osparc.FlashMessenger.logError(err, this.tr("Something went wrong while sharing the ") + resourceAlias));
    },

    _deleteMember: function(collaborator, item) {
      if (item) {
        item.setEnabled(false);
      }

      return osparc.store.Functions.removeCollaborator(this._serializedDataCopy, collaborator["gid"])
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

      osparc.store.Functions.updateCollaborator(this._serializedDataCopy, collaboratorGId, newAccessRights)
        .then(() => {
          this.fireDataEvent("updateAccessRights", this._serializedDataCopy);
          osparc.FlashMessenger.logAs(successMsg);
          this._reloadCollaboratorsList();
        })
        .catch(err => osparc.FlashMessenger.logError(err, failureMsg))
        .finally(() => {
          if (item) {
            item.setEnabled(true);
          }
        });
    },

    _promoteToEditor: function(collaborator, item) {
      const writeAccessRole = osparc.data.Roles.FUNCTION["write"];
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

    _demoteToUser: async function(collaborator, item) {
      const readAccessRole = osparc.data.Roles.FUNCTION["read"];
      const groupId = collaborator["gid"];
      const demoteToUser = (gid, itm) => {
        this.__make(
          gid,
          readAccessRole.accessRights,
          this.tr(`Successfully demoted to ${readAccessRole.label}`),
          this.tr(`Something went wrong while demoting to ${readAccessRole.label}`),
          itm
        );
      };

      const organization = osparc.store.Groups.getInstance().getOrganization(groupId);
      if (organization) {
        const msg = this.tr(`Demoting to ${readAccessRole.label} will remove write access to all the members of the Organization. Are you sure?`);
        const win = new osparc.ui.window.Confirmation(msg).set({
          caption: this.tr("Demote"),
          confirmAction: "delete",
          confirmText: this.tr("Yes")
        });
        win.center();
        win.open();
        win.addListener("close", () => {
          if (win.getConfirmed()) {
            demoteToUser(groupId, item);
          }
        }, this);
      } else {
        demoteToUser(groupId, item);
      }
    },

    _demoteToEditor: function(collaborator, item) {
      osparc.FlashMessenger.logAs(this.tr("Operation not available"), "WARNING");
    },
  }
});
