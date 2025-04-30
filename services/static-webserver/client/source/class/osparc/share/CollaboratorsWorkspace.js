/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.share.CollaboratorsWorkspace", {
  extend: osparc.share.Collaborators,

  /**
    * @param workspace {osparc.data.model.Workspace}
    */
  construct: function(workspace) {
    this.__workspace = workspace;
    this._resourceType = "workspace";

    const workspaceDataCopy = workspace.serialize();
    this.base(arguments, workspaceDataCopy, []);
  },

  statics: {
    canIDelete: function(myAccessRights) {
      return myAccessRights["delete"];
    },
  },

  members: {
    __workspace: null,

    _addEditors: function(gids) {
      if (gids.length === 0) {
        return;
      }

      const writeAccessRole = osparc.data.Roles.WORKSPACE["write"];
      const newCollaborators = {};
      gids.forEach(gid => newCollaborators[gid] = writeAccessRole.accessRights);
      osparc.store.Workspaces.getInstance().addCollaborators(this.__workspace.getWorkspaceId(), newCollaborators)
        .then(() => {
          const text = this.tr("Workspace successfully shared");
          osparc.FlashMessenger.logAs(text);
          this.fireDataEvent("updateAccessRights", this.__workspace.serialize());
          this._reloadCollaboratorsList();
        })
        .catch(err => osparc.FlashMessenger.logError(err, this.tr("Something went wrong while sharing the workspace")));
    },

    _deleteMember: function(collaborator, item) {
      if (item) {
        item.setEnabled(false);
      }

      osparc.store.Workspaces.getInstance().removeCollaborator(this.__workspace.getWorkspaceId(), collaborator["gid"])
        .then(() => {
          this.fireDataEvent("updateAccessRights", this.__workspace.serialize());
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

      osparc.store.Workspaces.getInstance().updateCollaborator(this.__workspace.getWorkspaceId(), collaboratorGId, newAccessRights)
        .then(() => {
          this.fireDataEvent("updateAccessRights", this.__workspace.serialize());
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
      const writeAccessRole = osparc.data.Roles.WORKSPACE["write"];
      this.__make(
        collaborator["gid"],
        writeAccessRole.accessRights,
        this.tr(`Successfully promoted to ${writeAccessRole.label}`),
        this.tr(`Something went wrong while promoting to ${writeAccessRole.label}`),
        item
      );
    },

    _promoteToOwner: function(collaborator, item) {
      const deleteAccessRole = osparc.data.Roles.WORKSPACE["delete"];
      this.__make(
        collaborator["gid"],
        deleteAccessRole.accessRights,
        this.tr(`Successfully promoted to ${deleteAccessRole.label}`),
        this.tr(`Something went wrong while promoting to ${deleteAccessRole.label}`),
        item
      );
    },

    _demoteToUser: async function(collaborator, item) {
      const readAccessRole = osparc.data.Roles.WORKSPACE["read"];
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

      const group = osparc.store.Groups.getInstance().getOrganization(groupId);
      if (group) {
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
      const writeAccessRole = osparc.data.Roles.WORKSPACE["write"];
      this.__make(
        collaborator["gid"],
        writeAccessRole.accessRights,
        this.tr(`Successfully demoted to ${writeAccessRole.label}`),
        this.tr(`Something went wrong while demoting to ${writeAccessRole.label}`),
        item
      );
    }
  }
});
