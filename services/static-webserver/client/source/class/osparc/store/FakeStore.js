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
      owner: 1,
      createdAt: "2024-07-11T06:28:28.527Z",
      lastModified: "2024-07-13T06:28:28.527Z",
      accessRights: {
        1: {
          read: true,
          write: true,
          delete: true
        }
      },
      sharedAccessRights: {
        1: {
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
      owner: 2,
      createdAt: "2024-07-13T06:28:28.527Z",
      lastModified: "2024-07-15T06:28:28.527Z",
      accessRights: {
        1: {
          read: true,
          write: true,
          delete: false
        }
      },
      sharedAccessRights: {
        1: {
          read: true,
          write: true,
          delete: false
        },
        2: {
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
      owner: 1,
      createdAt: "2024-07-16T06:28:28.527Z",
      lastModified: "2024-07-17T06:28:28.527Z",
      accessRights: {
        1: {
          read: true,
          write: true,
          delete: true
        }
      },
      sharedAccessRights: {
        1: {
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

    postFolder: function(folder) {
      this.__folders.push(folder);
    }
  }
});
