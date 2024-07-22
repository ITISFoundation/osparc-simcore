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


qx.Class.define("osparc.share.CollaboratorsFolder", {
  extend: osparc.share.Collaborators,

  /**
    * @param folder {osparc.data.model.Folder}
    */
  construct: function(folder) {
    this._resourceType = "folder";
    const folderDataCopy = folder.serialize();

    this.base(arguments, folderDataCopy, []);
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
    },

    __getDeleters: function(studyData) {
      const deleters = [];
      Object.entries(studyData["accessRights"]).forEach(([key, value]) => {
        if (value["delete"]) {
          deleters.push(key);
        }
      });
      return deleters;
    },

    // checks that if the user to remove is an owner, there will still be another owner
    checkRemoveCollaborator: function(studyData, gid) {
      const ownerGids = this.__getDeleters(studyData);
      if (ownerGids.includes(gid.toString())) {
        return ownerGids.length > 1;
      }
      return true;
    }
  },

  members: {
    _addEditors: function(gids) {
      if (gids.length === 0) {
        return;
      }

      const newCollaborators = {};
      gids.forEach(gid => {
        newCollaborators[gid] = this._resourceType === "study" ? this.self().getCollaboratorAccessRight() : this.self().getViewerAccessRight();
      });
      osparc.info.StudyUtils.addCollaborators(this._serializedDataCopy, newCollaborators)
        .then(() => {
          this.fireDataEvent("updateAccessRights", this._serializedDataCopy);
          const text = this.tr("User(s) successfully added.");
          osparc.FlashMessenger.getInstance().logAs(text);
          this._reloadCollaboratorsList();

          this.__pushNotifications(gids);
          this.__checkShareePermissions(gids);
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

      osparc.info.StudyUtils.removeCollaborator(this._serializedDataCopy, collaborator["gid"])
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

      osparc.info.StudyUtils.updateCollaborator(this._serializedDataCopy, collaboratorGId, newAccessRights)
        .then(() => {
          this.fireDataEvent("updateAccessRights", this._serializedDataCopy);
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
        this.tr(`${osparc.data.Roles.STUDY[1].label} successfully changed ${osparc.data.Roles.STUDY[2].label}`),
        this.tr(`Something went wrong changing ${osparc.data.Roles.STUDY[1].label} to ${osparc.data.Roles.STUDY[2].label}`),
        item
      );
    },

    _promoteToOwner: function(collaborator, item) {
      this.__make(
        collaborator["gid"],
        this.self().getOwnerAccessRight(),
        this.tr(`${osparc.data.Roles.STUDY[2].label} successfully changed to ${osparc.data.Roles.STUDY[3].label}`),
        this.tr(`Something went wrong changing ${osparc.data.Roles.STUDY[2].label} to ${osparc.data.Roles.STUDY[3].label}`),
        item
      );
    },

    _demoteToUser: async function(collaborator, item) {
      const groupId = collaborator["gid"];
      const demoteToUser = (gid, itm) => {
        this.__make(
          gid,
          this.self().getViewerAccessRight(),
          this.tr(`${osparc.data.Roles.STUDY[2].label} successfully changed to ${osparc.data.Roles.STUDY[1].label}`),
          this.tr(`Something went wrong changing ${osparc.data.Roles.STUDY[2].label} to ${osparc.data.Roles.STUDY[1].label}`),
          itm
        );
      };

      const groupData = await osparc.store.Store.getInstance().getGroup(groupId);
      const isOrganization = (groupData && !("id" in groupData));
      if (isOrganization) {
        const msg = this.tr(`Demoting to ${osparc.data.Roles.STUDY[1].label} will remove write access to all the members of the Organization. Are you sure?`);
        const win = new osparc.ui.window.Confirmation(msg).set({
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
        this.tr(`${osparc.data.Roles.STUDY[3].label} successfully changed to ${osparc.data.Roles.STUDY[2].label}`),
        this.tr(`Something went wrong changing ${osparc.data.Roles.STUDY[3].label} to ${osparc.data.Roles.STUDY[2].label}`),
        item
      );
    },

    __pushNotifications: function(gids) {
      // push 'FOLDER_SHARED' notification
      osparc.store.Store.getInstance().getPotentialCollaborators()
        .then(potentialCollaborators => {
          gids.forEach(gid => {
            if (gid in potentialCollaborators && "id" in potentialCollaborators[gid]) {
              // it's a user, not an organization
              const collab = potentialCollaborators[gid];
              const uid = collab["id"];
              if (this._resourceType === "study") {
                osparc.notification.Notifications.postNewStudy(uid, this._serializedDataCopy["uuid"]);
              } else {
                osparc.notification.Notifications.postNewTemplate(uid, this._serializedDataCopy["uuid"]);
              }
            }
          });
        });
    }
  }
});
