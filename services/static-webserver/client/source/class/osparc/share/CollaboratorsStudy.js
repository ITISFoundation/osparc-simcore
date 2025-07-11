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
    canCollaboratorBeRemoved: function(studyData, gid) {
      const ownerGids = this.__getDeleters(studyData);
      if (ownerGids.includes(gid.toString())) {
        return ownerGids.length > 1;
      }
      return true;
    },
  },

  members: {
    _addEditors: function(gids, newAccessRights) {
      if (gids.length === 0) {
        return;
      }

      const readAccessRole = osparc.data.Roles.STUDY["read"];
      const writeAccessRole = osparc.data.Roles.STUDY["write"];
      if (!newAccessRights) {
        newAccessRights = this._resourceType === "study" ? writeAccessRole.accessRights : readAccessRole.accessRights;
      }
      const resourceAlias = osparc.product.Utils.resourceTypeToAlias(this._resourceType, {firstUpperCase: true});
      const newCollaborators = {};
      gids.forEach(gid => {
        newCollaborators[gid] = newAccessRights;
      });
      osparc.store.Study.getInstance().addCollaborators(this._serializedDataCopy, newCollaborators)
        .then(() => {
          const text = resourceAlias + this.tr(" successfully shared");
          osparc.FlashMessenger.logAs(text);
          this.fireDataEvent("updateAccessRights", this._serializedDataCopy);
          this._reloadCollaboratorsList();

          this.__pushNotifications(gids);
          this.__checkShareePermissions(gids);
        })
        .catch(err => osparc.FlashMessenger.logError(err, this.tr("Something went wrong while sharing the ") + resourceAlias));
    },

    _deleteMember: function(collaborator, item) {
      if (item) {
        item.setEnabled(false);
      }

      return osparc.store.Study.getInstance().removeCollaborator(this._serializedDataCopy, collaborator["gid"])
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

      osparc.store.Study.getInstance().updateCollaborator(this._serializedDataCopy, collaboratorGId, newAccessRights)
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
      const writeAccessRole = osparc.data.Roles.STUDY["write"];
      this.__make(
        collaborator["gid"],
        writeAccessRole.accessRights,
        this.tr(`Successfully promoted to ${writeAccessRole.label}`),
        this.tr(`Something went wrong while promoting to ${writeAccessRole.label}`),
        item
      );
    },

    _promoteToOwner: function(collaborator, item) {
      const deleteAccessRole = osparc.data.Roles.STUDY["delete"];
      this.__make(
        collaborator["gid"],
        deleteAccessRole.accessRights,
        this.tr(`Successfully promoted to ${deleteAccessRole.label}`),
        this.tr(`Something went wrong while promoting to ${deleteAccessRole.label}`),
        item
      );
    },

    _demoteToUser: async function(collaborator, item) {
      const readAccessRole = osparc.data.Roles.STUDY["read"];
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
      const writeAccessRole = osparc.data.Roles.STUDY["write"];
      this.__make(
        collaborator["gid"],
        writeAccessRole.accessRights,
        this.tr(`Successfully demoted to ${writeAccessRole.label}`),
        this.tr(`Something went wrong while demoting to ${writeAccessRole.label}`),
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
          switch (this._resourceType) {
            case "study":
              osparc.notification.Notifications.pushStudyShared(uid, this._serializedDataCopy["uuid"]);
              break;
            case "template":
            case "tutorial":
              // do not push TEMPLATE_SHARED notification if users are not supposed to see the templates
              if (osparc.data.Permissions.getInstance().canRoleDo("user", "dashboard.templates.read")) {
                osparc.notification.Notifications.postNewTemplate(uid, this._serializedDataCopy["uuid"]);
              }
              break;
          }
        }
      });
    },

    __checkShareePermissions: function(gids) {
      if (gids.length === 0) {
        return;
      }
      osparc.share.ShareePermissions.checkShareePermissions(this._serializedDataCopy["uuid"], gids);
    }
  }
});
