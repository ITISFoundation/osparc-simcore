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

    this.__unknowns = [];
  },

  properties: {
    users: {
      check: "Array",
      init: [],
      nullable: false,
    },
  },

  members: {
    __unknowns: null,

    __fetchUser: function(userGroupId) {
      const params = {
        url: {
          gid: userGroupId
        }
      };
      return osparc.data.Resources.fetch("users", "get", params)
        .then(userData => {
          const user = this.addUser(userData[0]);
          return user;
        })
        .catch(() => {
          this.__unknowns.push(userGroupId);
          return null;
        });
    },

    getUser: async function(userGroupId, fetchIfNotFound = true) {
      if (this.__unknowns.includes(userGroupId)) {
        return null;
      }
      const userFound = this.getUsers().find(user => user.getGroupId() === userGroupId);
      if (userFound) {
        return userFound;
      }
      if (fetchIfNotFound) {
        try {
          const user = await this.__fetchUser(userGroupId);
          if (user) {
            return user;
          }
        } catch (error) {
          console.error(error);
        }
      }
      return null;
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
