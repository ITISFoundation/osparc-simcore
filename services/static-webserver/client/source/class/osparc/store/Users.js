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
    fetchUser: function(groupId) {
      const params = {
        url: {
          gid: groupId
        }
      };
      return osparc.data.Resources.fetch("users", "get", params)
        .then(userData => {
          const user = this.addUser(userData[0]);
          return user;
        });
    },

    getUser: function(groupId, fetchIfNotFound = true) {
      const userFound = this.getUsers().find(user => user.getGroupId() === groupId);
      if (userFound) {
        return new Promise(resolve => resolve(userFound));
      } else if (fetchIfNotFound) {
        return this.fetchUser(groupId);
      }
      return new Promise(reject => reject());
    },

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
