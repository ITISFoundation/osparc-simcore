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

    this.set({
      padding: 10,
    });

    this.getChildControl("thumbnail");
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
    "closeWindow": "qx.event.type.Event",
  },

  statics: {
    THUMBNAIL_SIZE: 90,
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "thumbnail":
          control = new osparc.ui.basic.Thumbnail(null, this.self().THUMBNAIL_SIZE, this.self().THUMBNAIL_SIZE).set({
            width: this.self().THUMBNAIL_SIZE,
            height: this.self().THUMBNAIL_SIZE,
            marginBottom: 10,
          });
          control.getChildControl("image").set({
            anonymous: true,
            decorator: "rounded",
          });
          this.addWidgetToTabs(control);
          break;
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
            user.setContactData(userData);
            // remove the displayed properties from the contact info
            Object.keys(qx.util.PropertyUtil.getProperties(osparc.data.model.User)).forEach(prop => delete userData[prop]);
            const extras = osparc.utils.Utils.convertKeysToTitles(userData);

            this.fireDataEvent("updateCaption", user.getUserName());
            this.getChildControl("thumbnail").setSource(user.createThumbnail(this.self().THUMBNAIL_SIZE));
            this.setUser(user);
            this.setExtras(extras);
          }
        })
        .catch(err => {
          osparc.FlashMessenger.logError(err);
          console.error(err);
          this.fireEvent("closeWindow");
        });
    },
  }
});
