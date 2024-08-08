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

  members: {
    foldersCached: null,

    fetchFolders: function(folderId = null) {
      return new Promise(resolve => {
        let promise = null;
        if (folderId) {
          const params = {
            "url": {
              folderId
            }
          };
          // osparc.data.Resources.getInstance().getAllPages("folders", params)
          promise = osparc.data.Resources.getInstance().fetch("folders", "getWithinFolder", params);
        } else {
          promise = osparc.data.Resources.getInstance().fetch("folders", "getRootFolders");
        }
        promise
          .then(foldersData => {
            foldersData.forEach(folderData => {
              const folder = new osparc.data.model.Folder(folderData);
              this.__addToCache(folder);
            });
            resolve();
          })
      });
    },

    postFolder: function(name, description, parentId = null) {
      return new Promise(resolve => {
        const newFolderData = {
          parentFolderId: parentId,
          name: name,
          description: description || "",
        };
        const params = {
          data: newFolderData
        };
        osparc.data.Resources.getInstance().fetch("folders", "post", params)
          .then(resp => {
            const foldersStore = osparc.store.Folders.getInstance();
            const folderId = resp["folderId"];
            foldersStore.fetchFolders(parentId)
              .then(() => {
                const newFolder = foldersStore.getFolder(folderId);
                resolve(newFolder);
              });
          });
      });
    },

    deleteFolder: function(folderId) {
      return new Promise((resolve, reject) => {
        const idx = this.foldersCached.findIndex(f => f.getFolderId() === folderId);
        if (idx > -1) {
          this.foldersCached.splice(idx, 1);
          resolve();
        } else {
          reject();
        }
      });
    },

    patchFolder: function(folderId, propKey, value) {
      return new Promise((resolve, reject) => {
        const folder = this.getFolder(folderId);
        const upKey = qx.lang.String.firstUp(propKey);
        const setter = "set" + upKey;
        if (folder && setter in folder) {
          folder[setter](value);
          folder.setLastModified(new Date());
          resolve();
        } else {
          reject();
        }
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
        this.foldersCached.push(folder);
      }
    }
  }
});
