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

qx.Class.define("osparc.store.Workspaces", {
  type: "static",

  construct: function() {
    this.base(arguments);

    this.foldersCached = [];
  },

  members: {
    foldersCached: null,

    fetchFolders: function(folderId = null) {
      if (osparc.auth.Data.getInstance().isGuest()) {
        return new Promise(resolve => {
          resolve([]);
        });
      }

      const params = {
        "url": {
          folderId
        }
      };
      return osparc.data.Resources.getInstance().getAllPages("folders", params)
        .then(foldersData => {
          const folders = [];
          foldersData.forEach(folderData => {
            const folder = new osparc.data.model.Folder(folderData);
            this.__addToCache(folder);
            folders.push(folder);
          });
          return folders;
        });
    },

    postFolder: function(name, description, parentId = null) {
      const newFolderData = {
        parentFolderId: parentId,
        name: name,
        description: description || "",
      };
      const params = {
        data: newFolderData
      };
      return osparc.data.Resources.getInstance().fetch("folders", "post", params)
        .then(folderData => {
          const newFolder = new osparc.data.model.Folder(folderData);
          this.__addToCache(newFolder);
          return newFolder;
        });
    },

    deleteFolder: function(folderId) {
      return new Promise((resolve, reject) => {
        const params = {
          "url": {
            folderId
          }
        };
        osparc.data.Resources.getInstance().fetch("folders", "delete", params)
          .then(() => {
            if (this.__deleteFromCache(folderId)) {
              resolve();
            } else {
              reject();
            }
          })
          .catch(err => reject(err));
      });
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
          .then(() => {
            const folder = this.getFolder(folderId);
            Object.keys(updateData).forEach(propKey => {
              const upKey = qx.lang.String.firstUp(propKey);
              const setter = "set" + upKey;
              if (folder && setter in folder) {
                folder[setter](updateData[propKey]);
              }
            });
            folder.setLastModified(new Date());
            this.__deleteFromCache(folderId);
            this.__addToCache(folder);
            resolve();
          })
          .catch(err => reject(err));
      });
    },

    addCollaborators: function(folderId, newCollaborators) {
      return new Promise((resolve, reject) => {
        const folder = this.getFolder(folderId);
        if (folder) {
          const accessRights = folder.getAccessRights();
          const newAccessRights = Object.assign(accessRights, newCollaborators);
          folder.set({
            accessRights: newAccessRights,
            lastModified: new Date()
          })
          resolve();
        } else {
          reject();
        }
      });
    },

    removeCollaborator: function(folderId, gid) {
      return new Promise((resolve, reject) => {
        const folder = this.getFolder(folderId);
        if (folder) {
          const accessRights = folder.getAccessRights();
          delete accessRights[gid];
          folder.set({
            accessRights: accessRights,
            lastModified: new Date()
          })
          resolve();
        } else {
          reject();
        }
      });
    },

    updateCollaborator: function(folderId, gid, newPermissions) {
      return new Promise((resolve, reject) => {
        const folder = this.getFolder(folderId);
        if (folder) {
          const accessRights = folder.getAccessRights();
          if (gid in accessRights) {
            accessRights[gid] = newPermissions;
            folder.set({
              accessRights: accessRights,
              lastModified: new Date()
            })
            resolve();
            return;
          }
        }
        reject();
      });
    },

    getFolders: function(parentId = null) {
      return this.foldersCached.filter(f => f.getParentId() === parentId);
    },

    getFolder: function(folderId = null) {
      return this.foldersCached.find(f => f.getFolderId() === folderId);
    },

    __addToCache: function(folder) {
      const found = this.foldersCached.find(f => f.getFolderId() === folder.getFolderId());
      if (!found) {
        this.foldersCached.unshift(folder);
      }
    },

    __deleteFromCache: function(folderId) {
      const idx = this.foldersCached.findIndex(f => f.getFolderId() === folderId);
      if (idx > -1) {
        this.foldersCached.splice(idx, 1);
        return true;
      }
      return false;
    }
  }
});
