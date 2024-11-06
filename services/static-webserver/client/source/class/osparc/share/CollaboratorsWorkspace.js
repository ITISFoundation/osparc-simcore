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
    }
  },

  members: {
    __workspace: null,

    _addEditors: function(gids) {
      if (gids.length === 0) {
        return;
      }

      const newCollaborators = {};
      gids.forEach(gid => newCollaborators[gid] = this.self().getCollaboratorAccessRight());
      osparc.store.Workspaces.getInstance().addCollaborators(this.__workspace.getWorkspaceId(), newCollaborators)
        .then(() => {
          this.fireDataEvent("updateAccessRights", this.__workspace.serialize());
          const text = this.tr("User(s) successfully added.");
          osparc.FlashMessenger.getInstance().logAs(text);
          this._reloadCollaboratorsList();
        })
        .catch(err => {
          console.error(err);
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went adding user(s)"), "ERROR");
        });
    },

    _deleteMember: function(collaborator, item) {
      if (item) {
        item.setEnabled(false);
      }

      osparc.store.Workspaces.getInstance().removeCollaborator(this.__workspace.getWorkspaceId(), collaborator["gid"])
        .then(() => {
          this.fireDataEvent("updateAccessRights", this.__workspace.serialize());
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

      osparc.store.Workspaces.getInstance().updateCollaborator(this.__workspace.getWorkspaceId(), collaboratorGId, newAccessRights)
        .then(() => {
          this.fireDataEvent("updateAccessRights", this.__workspace.serialize());
          osparc.FlashMessenger.getInstance().logAs(successMsg);
          this._reloadCollaboratorsList();
        })
        .catch(err => {
          console.error(err);
          osparc.FlashMessenger.getInstance().logAs(failureMsg, "ERROR");
        })
        .finally(() => {
          if (item) {
            item.setEnabled(true);
          }
        });
    },

    _promoteToEditor: function(collaborator, item) {
      this.__make(
        collaborator["gid"],
        this.self().getCollaboratorAccessRight(),
        this.tr(`${osparc.data.Roles.WORKSPACE[1].label} successfully changed ${osparc.data.Roles.WORKSPACE[2].label}`),
        this.tr(`Something went wrong changing ${osparc.data.Roles.WORKSPACE[1].label} to ${osparc.data.Roles.WORKSPACE[2].label}`),
        item
      );
    },

    _promoteToOwner: function(collaborator, item) {
      this.__make(
        collaborator["gid"],
        this.self().getOwnerAccessRight(),
        this.tr(`${osparc.data.Roles.WORKSPACE[2].label} successfully changed to ${osparc.data.Roles.WORKSPACE[3].label}`),
        this.tr(`Something went wrong changing ${osparc.data.Roles.WORKSPACE[2].label} to ${osparc.data.Roles.WORKSPACE[3].label}`),
        item
      );
    },

    _demoteToUser: async function(collaborator, item) {
      const groupId = collaborator["gid"];
      const demoteToUser = (gid, itm) => {
        this.__make(
          gid,
          this.self().getViewerAccessRight(),
          this.tr(`${osparc.data.Roles.WORKSPACE[2].label} successfully changed to ${osparc.data.Roles.WORKSPACE[1].label}`),
          this.tr(`Something went wrong changing ${osparc.data.Roles.WORKSPACE[2].label} to ${osparc.data.Roles.WORKSPACE[1].label}`),
          itm
        );
      };

      const groupData = await osparc.store.Store.getInstance().getGroup(groupId);
      const isOrganization = (groupData && !("id" in groupData));
      if (isOrganization) {
        const msg = this.tr(`Demoting to ${osparc.data.Roles.WORKSPACE[1].label} will remove write access to all the members of the Organization. Are you sure?`);
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
      this.__make(
        collaborator["gid"],
        this.self().getCollaboratorAccessRight(),
        this.tr(`${osparc.data.Roles.WORKSPACE[3].label} successfully changed to ${osparc.data.Roles.WORKSPACE[2].label}`),
        this.tr(`Something went wrong changing ${osparc.data.Roles.WORKSPACE[3].label} to ${osparc.data.Roles.WORKSPACE[2].label}`),
        item
      );
    }
  }
});
