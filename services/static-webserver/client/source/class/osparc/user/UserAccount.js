/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.user.UserAccount", {
  extend: osparc.ui.window.TabbedView,

  construct: function(userGroupId) {
    this.base(arguments);

    /*
    const miniProfile = osparc.desktop.account.MyAccount.createMiniProfileView().set({
      paddingRight: 10
    });
    this.addWidgetToTabs(miniProfile);
    */

    const profilePage = this.getChildControl("profile-page");
    const extras = this.getChildControl("extras-page");
    this.bind("user", profilePage, "user");
    this.bind("extras", extras, "extras");

    this.setUserGroupId(userGroupId);
  },

  properties: {
    userGroupId: {
      check: "Number",
      init: null,
      nullable: false,
      apply: "__applyUserGroupId",
    },

    user: {
      check: "osparc.data.model.User",
      init: null,
      nullable: false,
      event: "changeUser",
    },

    extras: {
      check: "Object",
      init: null,
      nullable: false,
      event: "changeExtras",
    },
  },

  events: {
    "updateCaption": "qx.event.type.Data",
  },

  statics: {
    THUMBNAIL_SIZE: 110,
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "profile-page":
          control = new osparc.user.UserProfile();
          this.addTab("Profile", "", control);
          break;
        case "extras-page":
          control = new osparc.user.UserExtras();
          this.addTab("Extras", "", control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyUserGroupId: function(userGroupId) {
      const params = {
        url: {
          gId: userGroupId
        }
      };
      osparc.data.Resources.fetch("poUsers", "searchByGroupId", params)
        .then(usersData => {
          if (usersData.length === 1) {
            const userData = usersData[0];
            const user = new osparc.data.model.User(userData);
            this.fireDataEvent("updateCaption", user.getUserName());
            this.setUser(user);
            this.setExtras(userData.extras || {});
          }
        })
        .catch(err => {
          console.error(err);
          this.close();
        });
    },
  }
});
