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

    this.__folders = [];
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
