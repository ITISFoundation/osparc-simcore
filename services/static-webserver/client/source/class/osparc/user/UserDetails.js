/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.user.UserDetails", {
  extend: osparc.ui.window.Window,

  construct: function(user) {
    this.base(arguments);

    this.setLayout(new qx.ui.layout.VBox(10));

    this.setUser(user);
  },

  statics: {
    WIDTH: 300,
    HEIGHT: 200,

    popUpInWindow: function(userModel) {
      const userDetails = new osparc.user.UserDetails(userModel);
      const title = userModel.getUsername();
      osparc.ui.window.Window.popUpInWindow(userDetails, title, this.WIDTH, this.HEIGHT).set({
        // layout: new qx.ui.layout.Grow(),
        // ...osparc.ui.window.TabbedWindow.DEFAULT_PROPS,
      });
    },

    GRID_POS: {
      USERNAME: 0,
      FULLNAME: 1,
      EMAIL: 2,
    }
  },

  properties: {
    user: {
      check: "osparc.data.model.User",
      init: true,
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
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
          this._add(control);
          break;
        case "thumbnail":
          control = new osparc.ui.basic.Thumbnail(null, 100, 100);
          this.getChildControl("top-layout").add(control);
          break;
        case "main-info": {
          const grid = new qx.ui.layout.Grid(5, 10);
          grid.setColumnFlex(1, 1);
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
      }
      return control || this.base(arguments, id);
    },

    __applyUser: function(user) {
      console.log("user", user);

      this.getChildControl("thumbnail").setSource(user.getThumbnail());
      this.getChildControl("username").setValue(user.getUsername());
      this.getChildControl("fullname").setValue(user.getFirstName() + " " + this.getLastName());
      this.getChildControl("email").setValue(user.getEmail());
    },
  }
});
