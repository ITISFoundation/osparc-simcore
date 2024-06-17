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
 *   - Share it with Organizations and/or Organization Members (Users)
 *   - Make other Users Owner
 *   - Remove users
 */

qx.Class.define("osparc.share.CollaboratorsStudy", {
  extend: osparc.share.Collaborators,

  /**
    * @param studyData {Object} Object containing the serialized Study Data
    */
  construct: function(studyData) {
    // this info is lost when we deepCloneStudyObject
    this._resourceType = studyData["resourceType"]; // study or template
    const studyDataCopy = osparc.data.model.Study.deepCloneStudyObject(studyData);

    osparc.data.Roles.createRolesStudyResourceInfo();

    const initCollabs = [];
    if (osparc.data.Permissions.getInstance().canDo("study.everyone.share")) {
      initCollabs.push(this.self().getEveryoneProductObj(this._resourceType === "study"));
      initCollabs.push(this.self().getEveryoneObj(this._resourceType === "study"));
    }

    this.base(arguments, studyDataCopy, initCollabs);
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
    },

    getEveryoneProductObj: function(isStudy) {
      const everyoneProductGroup = osparc.store.Store.getInstance().getEveryoneProductGroup();
      const everyone = osparc.utils.Utils.deepCloneObject(everyoneProductGroup);
      everyone["accessRights"] = isStudy ? this.getCollaboratorAccessRight() : this.getViewerAccessRight();
      return everyone;
    },

    getEveryoneObj: function(isStudy) {
      const everyoneGroup = osparc.store.Store.getInstance().getEveryoneGroup();
      const everyone = osparc.utils.Utils.deepCloneObject(everyoneGroup);
      everyone["accessRights"] = isStudy ? this.getCollaboratorAccessRight() : this.getViewerAccessRight();
      return everyone;
    }
  },

  members: {
    _canIDelete: function() {
      return osparc.data.model.Study.canIDelete(this._serializedDataCopy["accessRights"]);
    },

    _canIWrite: function() {
      return osparc.data.model.Study.canIWrite(this._serializedDataCopy["accessRights"]);
    },

    _addEditors: function(gids, cb) {
      if (gids.length === 0) {
        return;
      }

      const newAccessRights = this._serializedDataCopy["accessRights"];
      gids.forEach(gid => {
        newAccessRights[gid] = this._resourceType === "study" ? this.self().getCollaboratorAccessRight() : this.self().getViewerAccessRight();
      });
      osparc.info.StudyUtils.patchStudyData(this._serializedDataCopy, "accessRights", newAccessRights)
        .then(() => {
          this.fireDataEvent("updateAccessRights", this._serializedDataCopy);
          const text = this.tr("User(s) successfully added.");
          osparc.FlashMessenger.getInstance().logAs(text);
          this._reloadCollaboratorsList();

          this.__checkShareePermissions(gids);
        })
        .catch(err => {
          console.error(err);
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went adding user(s)"), "ERROR");
        })
        .finally(() => cb());

      // push 'STUDY_SHARED'/'TEMPLATE_SHARED' notification
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
    },

    __checkShareePermissions: function(gids) {
      if (gids.length === 0) {
        return;
      }

      const promises = [];
      gids.forEach(gid => {
        const params = {
          url: {
            "studyId": this._serializedDataCopy["uuid"],
            "gid": gid
          }
        };
        promises.push(osparc.data.Resources.fetch("studies", "checkShareePermissions", params));
      });
      Promise.all(promises)
        .then(values => {
          const noAccessible = values.filter(value => value["accessible"] === false);
          if (noAccessible.length) {
            const shareePermissions = new osparc.share.ShareePermissions(noAccessible);
            const win = osparc.ui.window.Window.popUpInWindow(shareePermissions, this.tr("Sharee permissions"), 500, 500, "@FontAwesome5Solid/exclamation-triangle/14").set({
              clickAwayClose: false,
              resizable: true,
              showClose: true
            });
            win.getChildControl("icon").set({
              textColor: "warning-yellow"
            });
          }
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

      osparc.info.StudyUtils.patchStudyData(this._serializedDataCopy, "accessRights", this._serializedDataCopy["accessRights"])
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
      osparc.info.StudyUtils.patchStudyData(this._serializedDataCopy, "accessRights", this._serializedDataCopy["accessRights"])
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
    }
  }
});
