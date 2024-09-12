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

qx.Class.define("osparc.store.Folders", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);

    this.foldersCached = [];
  },

  events: {
    "folderAdded": "qx.event.type.Data",
    "folderRemoved": "qx.event.type.Data",
  },

  members: {
    foldersCached: null,

    fetchFolders: function(folderId = null, workspaceId = null) {
      if (osparc.auth.Data.getInstance().isGuest()) {
        return new Promise(resolve => {
          resolve([]);
        });
      }

      const params = {
        "url": {
          workspaceId,
          folderId,
        }
      };
      return osparc.data.Resources.getInstance().getAllPages("folders", params)
        .then(foldersData => {
          const folders = [];
          foldersData.forEach(folderData => {
            const folder = this.__addToCache(folderData);
            folders.push(folder);
          });
          return folders;
        });
    },

    postFolder: function(name, parentFolderId = null, workspaceId = null) {
      const newFolderData = {
        name,
        parentFolderId,
        workspaceId,
      };
      const params = {
        data: newFolderData
      };
      return osparc.data.Resources.getInstance().fetch("folders", "post", params)
        .then(folderData => {
          const folder = this.__addToCache(folderData);
          this.fireDataEvent("folderAdded", folder);
          return folder;
        });
    },

    deleteFolder: function(folderId, workspaceId) {
      const params = {
        "url": {
          folderId
        }
      };
      return osparc.data.Resources.getInstance().fetch("folders", "delete", params)
        .then(() => {
          const folder = this.getFolder(folderId);
          if (folder) {
            this.__deleteFromCache(folderId, workspaceId);
            this.fireDataEvent("folderRemoved", folder);
          }
        })
        .catch(console.error);
    },

    putFolder: function(folderId, updateData) {
      return new Promise((resolve, reject) => {
        const params = {
          "url": {
            folderId
          },
          data: updateData
        };
        osparc.data.Resources.getInstance().fetch("folders", "update", params)
          .then(folderData => {
            this.__addToCache(folderData);
            resolve();
          })
          .catch(err => reject(err));
      });
    },

    getFolder: function(folderId = null) {
      return this.foldersCached.find(f => f.getFolderId() === folderId);
    },

    __addToCache: function(folderData) {
      let folder = this.foldersCached.find(f => f.getFolderId() === folderData["folderId"] && f.getWorkspaceId() === folderData["workspaceId"]);
      if (folder) {
        // put
        Object.keys(folderData).forEach(key => {
          if (key === "createdAt") {
            folder.set("createdAt", new Date(folderData["createdAt"]));
          } else if (key === "modifiedAt") {
            folder.set("lastModified", new Date(folderData["modifiedAt"]));
          } else {
            folder.set(key, folderData[key]);
          }
        });
      } else {
        // get and post
        folder = new osparc.data.model.Folder(folderData);
        this.foldersCached.unshift(folder);
      }
      return folder;
    },

    __deleteFromCache: function(folderId, workspaceId) {
      const idx = this.foldersCached.findIndex(f => f.getFolderId() === folderId && f.getWorkspaceId() === workspaceId);
      if (idx > -1) {
        this.foldersCached.splice(idx, 1);
        return true;
      }
      return false;
    }
  }
});
