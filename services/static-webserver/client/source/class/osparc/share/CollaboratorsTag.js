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
  },

  members: {
    __tag: null,

    _addEditors: function(gids) {
      if (gids.length === 0) {
        return;
      }

      const readAccessRole = osparc.data.Roles.STUDY["read"];
      const newCollaborators = {};
      gids.forEach(gid => newCollaborators[gid] = readAccessRole.accessRights);
      osparc.store.Tags.getInstance().addCollaborators(this.__tag.getTagId(), newCollaborators)
        .then(() => {
          const text = this.tr("Tag successfully shared");
          osparc.FlashMessenger.logAs(text);
          this.fireDataEvent("updateAccessRights", this.__tag.serialize());
          this._reloadCollaboratorsList();
        })
        .catch(err => osparc.FlashMessenger.logError(err, this.tr("Something went wrong while sharing the tag")));
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
        .catch(err => osparc.FlashMessenger.logError(err, this.tr("Something went wrong while removing ") + collaborator["name"]))
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
      this.__make(
        collaborator["gid"],
        readAccessRole.accessRights,
        this.tr(`Successfully demoted to ${readAccessRole.label}`),
        this.tr(`Something went wrong while demoting to ${readAccessRole.label}`),
        item
      );
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
    }
  }
});
