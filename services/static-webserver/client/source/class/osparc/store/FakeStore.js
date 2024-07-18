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

qx.Class.define("osparc.store.FakeStore", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);

    this.__folders = [{
      id: 1,
      parentFolder: null,
      name: "Folder 1",
      description: "Description Folder One",
      owner: 3,
      createdAt: "2024-07-11T06:28:28.527Z",
      lastModified: "2024-07-13T06:28:28.527Z",
      accessRights: {
        read: true,
        write: true,
        delete: true
      },
      sharedAccessRights: {
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
      accessRights: {
        read: true,
        write: true,
        delete: false
      },
      sharedAccessRights: {
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
      },
    }, {
      id: 3,
      parentFolder: 1,
      name: "Folder 3",
      description: "Description Folder Three",
      owner: 3,
      createdAt: "2024-07-16T06:28:28.527Z",
      lastModified: "2024-07-17T06:28:28.527Z",
      accessRights: {
        read: true,
        write: true,
        delete: true
      },
      sharedAccessRights: {
        3: {
          read: true,
          write: true,
          delete: true
        }
      }
    }];
  },

  members: {
    __folders: null,

    getFolders: function(parentFolder = null) {
      return new Promise(resolve => {
        resolve(this.__folders.filter(folder => folder.parentFolder === parentFolder));
      });
    },

    postFolder: function(folderName) {
      const myGroupId = osparc.auth.Data.getInstance().getGroupId();
      const newFolder = {
        id: Math.floor(Math.random() * 1000),
        parentFolder: null,
        name: folderName,
        description: "Description",
        owner: myGroupId,
        createdAt: new Date().toString(),
        lastModified: new Date().toString(),
        accessRights: {
          read: true,
          write: true,
          delete: true
        },
        sharedAccessRights: {},
      };
      newFolder["sharedAccessRights"][myGroupId] = {
        read: true,
        write: true,
        delete: true
      };
      this.__folders.push(newFolder);
      return new Promise(resolve => resolve(newFolder));
    },

    patchFolder: function(folderId, propKey, value) {
      return new Promise((resolve, reject) => {
        const folderData = this.__folders.filter(folder => folder.id === folderId);
        if (folderData && propKey in folderData) {
          folderData[propKey] = value;
          resolve();
        } else {
          reject();
        }
      });
    }
  }
});
