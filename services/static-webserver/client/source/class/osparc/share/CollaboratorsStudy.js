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

    this.base(arguments, studyDataCopy);
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
  },

  members: {
    _addEditors: function(gids) {
      if (gids.length === 0) {
        return;
      }

      const resourceAlias = this._resourceType === "template" ?
        osparc.product.Utils.getTemplateAlias({firstUpperCase: true}) :
        osparc.product.Utils.getStudyAlias({firstUpperCase: true});
      const newCollaborators = {};
      gids.forEach(gid => {
        newCollaborators[gid] = this._resourceType === "study" ? this.self().getCollaboratorAccessRight() : this.self().getViewerAccessRight();
      });
      osparc.info.StudyUtils.addCollaborators(this._serializedDataCopy, newCollaborators)
        .then(() => {
          const text = resourceAlias + this.tr(" successfully shared");
          osparc.FlashMessenger.getInstance().logAs(text);
          this.fireDataEvent("updateAccessRights", this._serializedDataCopy);
          this._reloadCollaboratorsList();

          this.__pushNotifications(gids);
          this.__checkShareePermissions(gids);
        })
        .catch(err => {
          console.error(err);
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong sharing the ") + resourceAlias, "ERROR");
        });
    },

    _deleteMember: function(collaborator, item) {
      if (item) {
        item.setEnabled(false);
      }

      return osparc.info.StudyUtils.removeCollaborator(this._serializedDataCopy, collaborator["gid"])
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
        this.tr(`Successfully promoted to ${osparc.data.Roles.STUDY[2].label}`),
        this.tr(`Something went wrong promoting to ${osparc.data.Roles.STUDY[2].label}`),
        item
      );
    },

    _promoteToOwner: function(collaborator, item) {
      this.__make(
        collaborator["gid"],
        this.self().getOwnerAccessRight(),
        this.tr(`Successfully promoted to ${osparc.data.Roles.STUDY[3].label}`),
        this.tr(`Something went wrong promoting to ${osparc.data.Roles.STUDY[3].label}`),
        item
      );
    },

    _demoteToUser: async function(collaborator, item) {
      const groupId = collaborator["gid"];
      const demoteToUser = (gid, itm) => {
        this.__make(
          gid,
          this.self().getViewerAccessRight(),
          this.tr(`Successfully demoted to ${osparc.data.Roles.STUDY[1].label}`),
          this.tr(`Something went wrong demoting to ${osparc.data.Roles.STUDY[1].label}`),
          itm
        );
      };

      const organization = osparc.store.Groups.getInstance().getOrganization(groupId);
      if (organization) {
        const msg = this.tr(`Demoting to ${osparc.data.Roles.STUDY[1].label} will remove write access to all the members of the Organization. Are you sure?`);
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
        this.tr(`Successfully demoted to ${osparc.data.Roles.STUDY[2].label}`),
        this.tr(`Something went wrong demoting to ${osparc.data.Roles.STUDY[2].label}`),
        item
      );
    },

    __pushNotifications: function(gids) {
      // push 'STUDY_SHARED'/'TEMPLATE_SHARED' notification
      const potentialCollaborators = osparc.store.Groups.getInstance().getPotentialCollaborators()
      gids.forEach(gid => {
        if (gid in potentialCollaborators && "getUserId" in potentialCollaborators[gid]) {
          // it's a user, not an organization
          const uid = potentialCollaborators[gid].getUserId();
          if (this._resourceType === "study") {
            osparc.notification.Notifications.postNewStudy(uid, this._serializedDataCopy["uuid"]);
          } else if (this._resourceType === "template") {
            // do not push TEMPLATE_SHARED notification if users are not supposed to see the templates
            if (osparc.data.Permissions.getInstance().canRoleDo("user", "dashboard.templates.read")) {
              osparc.notification.Notifications.postNewTemplate(uid, this._serializedDataCopy["uuid"]);
            }
          }
        }
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
    }
  }
});
