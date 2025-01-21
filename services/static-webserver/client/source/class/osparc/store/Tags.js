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

qx.Class.define("osparc.store.Tags", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);

    this.tagsCached = [];
  },

  events: {
    "tagsChanged": "qx.event.type.Data",
  },

  members: {
    tagsCached: null,

    fetchTags: function() {
      if (osparc.auth.Data.getInstance().isGuest()) {
        return new Promise(resolve => {
          resolve([]);
        });
      }

      return osparc.data.Resources.get("tags")
        .then(tagsData => {
          const tags = [];
          tagsData.forEach(tagData => {
            const tag = this.__addToCache(tagData);
            tags.push(tag);
            this.fetchAccessRights(tag);
          });
          return tags;
        });
    },

    getTags: function() {
      return this.tagsCached;
    },

    getTag: function(tagId = null) {
      return this.tagsCached.find(f => f.getTagId() === tagId);
    },

    postTag: function(newTagData) {
      const params = {
        data: newTagData
      };
      return osparc.data.Resources.getInstance().fetch("tags", "post", params)
        .then(tagData => {
          const tag = this.__addToCache(tagData);
          this.fireDataEvent("tagsChanged", tag);
          return tag;
        });
    },

    deleteTag: function(tagId) {
      const params = {
        url: {
          tagId
        }
      };
      return osparc.data.Resources.getInstance().fetch("tags", "delete", params)
        .then(() => {
          const tag = this.getTag(tagId);
          if (tag) {
            this.__deleteFromCache(tagId);
            this.fireDataEvent("tagsChanged", tag);
          }
        })
        .catch(console.error);
    },

    patchTag: function(tagId, updateData) {
      const params = {
        url: {
          tagId
        },
        data: updateData
      };
      return osparc.data.Resources.getInstance().fetch("tags", "patch", params)
        .then(tagData => {
          if ("accessRights" in tagData) {
            // accessRights are not patched in this endpoint
            delete tagData["accessRights"];
          }
          return this.__addToCache(tagData);
        })
        .catch(console.error);
    },

    fetchAccessRights: function(tag) {
      const params = {
        url: {
          "tagId": tag.getTagId()
        }
      };
      return osparc.data.Resources.fetch("tags", "getAccessRights", params)
        .then(accessRightsArray => {
          const accessRights = {};
          accessRightsArray.forEach(ar => accessRights[ar.gid] = ar);
          tag.setAccessRights(accessRights)
        })
        .catch(err => console.error(err));
    },

    addCollaborators: function(tagId, newCollaborators) {
      const promises = [];
      Object.keys(newCollaborators).forEach(groupId => {
        const params = {
          url: {
            tagId,
            groupId,
          },
          data: newCollaborators[groupId]
        };
        promises.push(osparc.data.Resources.fetch("tags", "postAccessRights", params));
      });
      return Promise.all(promises)
        .then(() => {
          const tag = this.getTag(tagId);
          const newAccessRights = tag.getAccessRights();
          Object.keys(newCollaborators).forEach(gid => {
            newAccessRights[gid] = newCollaborators[gid];
          });
          tag.set({
            accessRights: newAccessRights,
          });
        })
        .catch(console.error);
    },

    removeCollaborator: function(tagId, groupId) {
      const params = {
        url: {
          tagId,
          groupId,
        }
      };
      return osparc.data.Resources.fetch("tags", "deleteAccessRights", params)
        .then(() => {
          const tag = this.getTag(tagId);
          const newAccessRights = tag.getAccessRights();
          delete newAccessRights[groupId];
          tag.set({
            accessRights: newAccessRights,
          });
        })
        .catch(console.error);
    },

    updateCollaborator: function(tagId, groupId, newPermissions) {
      const params = {
        url: {
          tagId,
          groupId,
        },
        data: newPermissions
      };
      return osparc.data.Resources.fetch("tags", "putAccessRights", params)
        .then(() => {
          const tag = this.getTag(tagId);
          const newAccessRights = tag.getAccessRights();
          newAccessRights[groupId] = newPermissions;
          tag.set({
            accessRights: tag.newAccessRights,
          });
        })
        .catch(console.error);
    },

    __addToCache: function(tagData) {
      let tag = this.tagsCached.find(f => f.getTagId() === tagData["id"]);
      if (tag) {
        const props = Object.keys(qx.util.PropertyUtil.getProperties(osparc.data.model.Tag));
        // put
        Object.keys(tagData).forEach(key => {
          if (props.includes(key)) {
            tag.set(key, tagData[key]);
          }
        });
      } else {
        // get and post
        tag = new osparc.data.model.Tag(tagData);
        this.tagsCached.unshift(tag);
      }
      return tag;
    },

    __deleteFromCache: function(tagId) {
      const idx = this.tagsCached.findIndex(f => f.getTagId() === tagId);
      if (idx > -1) {
        this.tagsCached.splice(idx, 1);
        return true;
      }
      return false;
    }
  }
});
