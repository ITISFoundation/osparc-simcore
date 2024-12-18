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

  properties: {
    users: {
      check: "Array",
      init: [],
      nullable: false,
    },
  },

  members: {
    addUser: function(userData) {
      const user = new osparc.data.model.User(userData);
      const userFound = this.getUsers().find(usr => usr.getGroupId() === user.getGroupId());
      if (!userFound) {
        this.getUsers().push(user);
      }
      return user;
    },

    searchUsers: function(text) {
      const params = {
        data: {
          match: text
        }
      };
      return osparc.data.Resources.fetch("users", "search", params)
        .then(usersData => {
          const users = [];
          usersData.forEach(userData => users.push(this.addUser(userData)));
          return users;
        });
    },
  }
});
