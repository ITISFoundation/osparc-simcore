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


qx.Class.define("osparc.share.CollaboratorsTag", {
  extend: osparc.share.Collaborators,

  /**
    * @param tag {osparc.data.model.Tag}
    */
  construct: function(tag) {
    this.__tag = tag;
    this._resourceType = "tag";

    const tagDataCopy = tag.serialize();
    this.base(arguments, tagDataCopy, []);
  },

  statics: {
    canIWrite: function(myAccessRights) {
      return myAccessRights["write"];
    },

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
    __tag: null,

    _addEditors: function(gids) {
      if (gids.length === 0) {
        return;
      }

      const newCollaborators = {};
      gids.forEach(gid => newCollaborators[gid] = this.self().getViewerAccessRight());
      osparc.store.Tags.getInstance().addCollaborators(this.__tag.getTagId(), newCollaborators)
        .then(() => {
          const text = this.tr("Tag successfully shared");
          osparc.FlashMessenger.logAs(text);
          this.fireDataEvent("updateAccessRights", this.__tag.serialize());
          this._reloadCollaboratorsList();
        })
        .catch(err => {
          console.error(err);
          osparc.FlashMessenger.logAs(this.tr("Something went wrong sharing the Tag"), "ERROR");
        });
    },

    _deleteMember: function(collaborator, item) {
      if (item) {
        item.setEnabled(false);
      }

      osparc.store.Tags.getInstance().removeCollaborator(this.__tag.getTagId(), collaborator["gid"])
        .then(() => {
          this.fireDataEvent("updateAccessRights", this.__tag.serialize());
          osparc.FlashMessenger.logAs(collaborator["name"] + this.tr(" successfully removed"));
          this._reloadCollaboratorsList();
        })
        .catch(err => {
          console.error(err);
          osparc.FlashMessenger.logAs(this.tr("Something went wrong removing ") + collaborator["name"], "ERROR");
        })
        .finally(() => {
          if (item) {
            item.setEnabled(true);
          }
        });
    },

    __make: function(collaboratorGId, newAccessRights, successMsg, failureMsg, item) {
      item.setEnabled(false);

      osparc.store.Tags.getInstance().updateCollaborator(this.__tag.getTagId(), collaboratorGId, newAccessRights)
        .then(() => {
          this.fireDataEvent("updateAccessRights", this.__tag.serialize());
          osparc.FlashMessenger.logAs(successMsg);
          this._reloadCollaboratorsList();
        })
        .catch(err => {
          console.error(err);
          osparc.FlashMessenger.logAs(failureMsg, "ERROR");
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
      this.__make(
        collaborator["gid"],
        this.self().getViewerAccessRight(),
        this.tr(`Successfully demoted to ${osparc.data.Roles.STUDY[1].label}`),
        this.tr(`Something went wrong demoting to ${osparc.data.Roles.STUDY[1].label}`),
        item
      );
    },

    _demoteToEditor: function(collaborator, item) {
      this.__make(
        collaborator["gid"],
        this.self().getCollaboratorAccessRight(),
        this.tr(`Successfully demoted to ${osparc.data.Roles.STUDY[2].label}`),
        this.tr(`Something went wrong demoting to ${osparc.data.Roles.STUDY[2].label}`),
        item
      );
    }
  }
});
