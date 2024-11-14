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
    "tagAdded": "qx.event.type.Data",
    "tagRemoved": "qx.event.type.Data",
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
          });
          return tags;
        });
    },

    getTags: function() {
      return this.tagsCached;
    },

    postTag: function(newTagData) {
      const params = {
        data: newTagData
      };
      return osparc.data.Resources.getInstance().fetch("tags", "post", params)
        .then(tagData => {
          const tag = this.__addToCache(tagData);
          this.fireDataEvent("tagAdded", tag);
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
            this.fireDataEvent("tagRemoved", tag);
          }
        })
        .catch(console.error);
    },

    putTag: function(tagId, updateData) {
      const params = {
        url: {
          tagId
        },
        data: updateData
      };
      return osparc.data.Resources.getInstance().fetch("tags", "put", params)
        .then(tagData => {
          return this.__addToCache(tagData);
        })
        .catch(console.error);
    },

    getTag: function(tagId = null) {
      return this.tagsCached.find(f => f.getTagId() === tagId);
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
