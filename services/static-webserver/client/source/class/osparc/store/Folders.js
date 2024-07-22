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

    this.fetchFolders();
  },

  statics: {
    FOLDER_DATA_INIT: [{
      id: 1,
      parentFolder: null,
      name: "Folder 1",
      description: "Description Folder One",
      owner: 3,
      createdAt: "2024-07-11T06:28:28.527Z",
      lastModified: "2024-07-13T06:28:28.527Z",
      myAccessRights: {
        read: true,
        write: true,
        delete: true
      },
      accessRights: {
        3: {
          read: true,
          write: true,
          delete: true
        }
      },
    }, {
      id: 2,
      parentFolder: null,
      name: "Folder 2",
      description: "Description Folder Two",
      owner: 3,
      createdAt: "2024-07-13T06:28:28.527Z",
      lastModified: "2024-07-15T06:28:28.527Z",
      myAccessRights: {
        read: true,
        write: true,
        delete: true
      },
      accessRights: {
        3: {
          read: true,
          write: true,
          delete: true
        },
        9: {
          read: true,
          write: true,
          delete: false
        }
      },
    }, {
      id: 3,
      parentFolder: 1,
      name: "Folder 3",
      description: "Description Folder Three",
      owner: 3,
      createdAt: "2024-07-16T06:28:28.527Z",
      lastModified: "2024-07-17T06:28:28.527Z",
      myAccessRights: {
        read: true,
        write: true,
        delete: true
      },
      accessRights: {
        3: {
          read: true,
          write: true,
          delete: true
        }
      }
    }, {
      id: 4,
      parentFolder: null,
      name: "Folder 4",
      description: "Description Folder Four",
      owner: 3,
      createdAt: "2024-07-17T06:28:28.527Z",
      lastModified: "2024-07-18T06:28:28.527Z",
      myAccessRights: {
        read: true,
        write: true,
        delete: false
      },
      accessRights: {
        3: {
          read: true,
          write: true,
          delete: false
        },
        9: {
          read: true,
          write: true,
          delete: true
        }
      }
    }, {
      id: 5,
      parentFolder: null,
      name: "Folder 5",
      description: "Description Folder Five",
      owner: 3,
      createdAt: "2024-07-18T06:28:28.527Z",
      lastModified: "2024-07-18T07:28:28.527Z",
      myAccessRights: {
        read: true,
        write: false,
        delete: false
      },
      accessRights: {
        3: {
          read: true,
          write: false,
          delete: false
        },
        9: {
          read: true,
          write: true,
          delete: true
        }
      },
    }]
  },

  members: {
    foldersCached: null,

    fetchFolders: function(parentId = null) {
      return new Promise(resolve => {
        this.self().FOLDER_DATA_INIT.forEach(folderData => {
          if (folderData.parentFolder === parentId) {
            const folder = new osparc.data.model.Folder(folderData);
            this.__addToCache(folder);
          }
        });
        resolve();
      });
    },

    postFolder: function(name, description, parentId = null) {
      return new Promise(resolve => {
        const myGroupId = osparc.auth.Data.getInstance().getGroupId();
        const newFolderData = {
          id: Math.floor(Math.random() * 1000),
          parentFolder: parentId,
          name: name,
          description: description || "",
          owner: myGroupId,
          createdAt: new Date().toString(),
          lastModified: new Date().toString(),
          myAccessRights: {
            read: true,
            write: true,
            delete: true
          },
          accessRights: {},
        };
        newFolderData["accessRights"][myGroupId] = {
          read: true,
          write: true,
          delete: true
        };
        const newFolder = new osparc.data.model.Folder(newFolderData);
        this.__addToCache(newFolder);
        resolve(newFolder)
      });
    },

    deleteFolder: function(folderId) {
      return new Promise((resolve, reject) => {
        const idx = this.foldersCached.findIndex(f => f.getId() === folderId);
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
      return this.foldersCached.find(f => f.getId() === folderId);
    },

    __addToCache: function(folder) {
      const found = this.foldersCached.find(f => f.getId() === folder.getId());
      if (!found) {
        this.foldersCached.push(folder);
      }
    }
  }
});
