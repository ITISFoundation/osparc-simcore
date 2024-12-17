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

qx.Class.define("osparc.store.Users", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);

    this.usersCached = [];
  },

  members: {
    addUser: function(userData) {
      const userFound = this.usersCached.find(user => user.getGroupId() === userData["groupId"]);
      if (!userFound) {
        const user = new osparc.data.model.User(userData);
        this.usersCached.push(user);
      }
    },
  }
});
