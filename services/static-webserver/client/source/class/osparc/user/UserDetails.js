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

qx.Class.define("osparc.user.UserDetails", {
  extend: osparc.ui.window.Window,

  construct: function(userGroupId) {
    this.base(arguments);

    this.set({
      layout: new qx.ui.layout.VBox(10),
      autoDestroy: true,
      showMaximize: false,
      showMinimize: false,
      clickAwayClose: true,
    });

    this.setUserGroupId(userGroupId);
  },

  statics: {
    WIDTH: 300,
    HEIGHT: 200,

    GRID_POS: {
      USERNAME: 0,
      FULLNAME: 1,
      EMAIL: 2,
      USER_ID: 3,
      GROUP_ID: 4,
    }
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
      apply: "__applyUser",
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "top-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(20));
          this.add(control);
          break;
        case "thumbnail":
          control = new osparc.ui.basic.Thumbnail(null, 100, 100);
          control.getChildControl("image").set({
            anonymous: true,
            decorator: "rounded",
          });
          this.getChildControl("top-layout").add(control);
          break;
        case "main-info": {
          const grid = new qx.ui.layout.Grid(10, 6);
          grid.setColumnFlex(1, 1);
          grid.setColumnAlign(0, "right", "middle");
          control = new qx.ui.container.Composite(grid);
          this.getChildControl("top-layout").add(control, {
            flex: 1
          });
          break;
        }
        case "username": {
          const title = new qx.ui.basic.Label("Username");
          this.getChildControl("main-info").add(title, {
            row: this.self().GRID_POS.USERNAME,
            column: 0
          });
          control = new qx.ui.basic.Label();
          this.getChildControl("main-info").add(control, {
            row: this.self().GRID_POS.USERNAME,
            column: 1
          });
          break;
        }
        case "fullname": {
          const title = new qx.ui.basic.Label("Full Name");
          this.getChildControl("main-info").add(title, {
            row: this.self().GRID_POS.FULLNAME,
            column: 0
          });
          control = new qx.ui.basic.Label();
          this.getChildControl("main-info").add(control, {
            row: this.self().GRID_POS.FULLNAME,
            column: 1
          });
          break;
        }
        case "email": {
          const title = new qx.ui.basic.Label("Email");
          this.getChildControl("main-info").add(title, {
            row: this.self().GRID_POS.EMAIL,
            column: 0
          });
          control = new qx.ui.basic.Label();
          this.getChildControl("main-info").add(control, {
            row: this.self().GRID_POS.EMAIL,
            column: 1
          });
          break;
        }
        case "user-id": {
          const title = new qx.ui.basic.Label("User ID");
          this.getChildControl("main-info").add(title, {
            row: this.self().GRID_POS.USER_ID,
            column: 0
          });
          control = new qx.ui.basic.Label();
          this.getChildControl("main-info").add(control, {
            row: this.self().GRID_POS.USER_ID,
            column: 1
          });
          break;
        }
        case "group-id": {
          const title = new qx.ui.basic.Label("Group ID");
          this.getChildControl("main-info").add(title, {
            row: this.self().GRID_POS.GROUP_ID,
            column: 0
          });
          control = new qx.ui.basic.Label();
          this.getChildControl("main-info").add(control, {
            row: this.self().GRID_POS.GROUP_ID,
            column: 1
          });
          break;
        }
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
            // curate data
            userData["groupId"] = userGroupId;
            userData["userId"] = -1; // fix this
            userData["userName"] = "userName"; // fix this
            const user = new osparc.data.model.User(userData);
            this.setUser(user);
          }
        })
        .catch(err => {
          console.error(err);
          this.close();
        });
    },

    __applyUser: function(user) {
      this.setCaption(user.getUsername());

      this.getChildControl("thumbnail").setSource(user.createThumbnail(96));
      this.getChildControl("username").setValue(user.getUsername());
      this.getChildControl("fullname").setValue([user.getFirstName(), user.getLastName()].filter(Boolean).join(" "));
      this.getChildControl("email").setValue(user.getEmail());
      this.getChildControl("user-id").setValue(String(user.getUserId()));
      this.getChildControl("group-id").setValue(String(user.getGroupId()));
    },
  }
});
