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
      accessRights: {
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
      accessRights: {
        1: {
          read: true,
          write: false,
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
      accessRights: {
        1: {
          read: true,
          write: true,
          delete: false
        }
      },
    }];
  },

  members: {
    __folders: null,

    getFolders: function(parentFolder) {
      return new Promise(resolve => {
        if (parentFolder) {
          resolve(this.__folders.filter(folder => folder.parentFolder === parentFolder));
          return;
        }
        resolve(this.__folders);
        return;
      });
    },

    postFolder: function(folder) {
      this.__folders.push(folder);
    }
  }
});
