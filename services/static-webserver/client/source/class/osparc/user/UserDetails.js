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
      contentPadding: 10,
      width: this.self().WIDTH,
      height: this.self().HEIGHT,
    });

    this.setUserGroupId(userGroupId);
  },

  statics: {
    WIDTH: 400,
    HEIGHT: 600,
    THUMBNAIL_SIZE: 110,

    TOP_GRID: {
      USERNAME: 0,
      FULLNAME: 1,
      EMAIL: 2,
      PHONE: 3,
      USER_ID: 4,
      GROUP_ID: 5,
    },

    MIDDLE_GRID: {
      INSTITUTION: 0,
      ADDRESS: 1,
      CITY: 2,
      STATE: 3,
      COUNTRY: 4,
      POSTAL_CODE: 5,
    },
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
    __remainingUserData: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "top-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(30));
          this.add(control);
          break;
        case "thumbnail":
          control = new osparc.ui.basic.Thumbnail(null, this.self().THUMBNAIL_SIZE, this.self().THUMBNAIL_SIZE).set({
            width: this.self().THUMBNAIL_SIZE,
            height: this.self().THUMBNAIL_SIZE,
          });
          control.getChildControl("image").set({
            anonymous: true,
            decorator: "rounded",
          });
          this.getChildControl("top-layout").add(control);
          break;
        case "top-info": {
          const grid = new qx.ui.layout.Grid(10, 6);
          grid.setColumnWidth(0, 80);
          grid.setColumnFlex(1, 1);
          grid.setColumnAlign(0, "right", "middle");
          control = new qx.ui.container.Composite(grid);
          this.getChildControl("top-layout").add(control, {
            flex: 1
          });
          break;
        }
        case "middle-info": {
          const grid = new qx.ui.layout.Grid(10, 6);
          grid.setColumnWidth(0, 80);
          grid.setColumnFlex(1, 1);
          grid.setColumnAlign(0, "right", "middle");
          control = new qx.ui.container.Composite(grid);
          this.add(control);
          break;
        }
        case "userName": {
          this.getChildControl("top-info").add(new qx.ui.basic.Label("UserName"), {
            row: this.self().TOP_GRID.USERNAME,
            column: 0
          });
          control = new qx.ui.basic.Label();
          this.getChildControl("top-info").add(control, {
            row: this.self().TOP_GRID.USERNAME,
            column: 1
          });
          break;
        }
        case "fullname": {
          this.getChildControl("top-info").add(new qx.ui.basic.Label("Full Name"), {
            row: this.self().TOP_GRID.FULLNAME,
            column: 0
          });
          control = new qx.ui.basic.Label();
          this.getChildControl("top-info").add(control, {
            row: this.self().TOP_GRID.FULLNAME,
            column: 1
          });
          break;
        }
        case "email": {
          this.getChildControl("top-info").add(new qx.ui.basic.Label("Email"), {
            row: this.self().TOP_GRID.EMAIL,
            column: 0
          });
          control = new qx.ui.basic.Label();
          this.getChildControl("top-info").add(control, {
            row: this.self().TOP_GRID.EMAIL,
            column: 1
          });
          break;
        }
        case "phone": {
          this.getChildControl("top-info").add(new qx.ui.basic.Label("Phone"), {
            row: this.self().TOP_GRID.PHONE,
            column: 0
          });
          control = new qx.ui.basic.Label();
          this.getChildControl("top-info").add(control, {
            row: this.self().TOP_GRID.PHONE,
            column: 1
          });
          break;
        }
        case "user-id": {
          this.getChildControl("top-info").add(new qx.ui.basic.Label("User ID"), {
            row: this.self().TOP_GRID.USER_ID,
            column: 0
          });
          control = new qx.ui.basic.Label();
          this.getChildControl("top-info").add(control, {
            row: this.self().TOP_GRID.USER_ID,
            column: 1
          });
          break;
        }
        case "group-id": {
          this.getChildControl("top-info").add(new qx.ui.basic.Label("Group ID"), {
            row: this.self().TOP_GRID.GROUP_ID,
            column: 0
          });
          control = new qx.ui.basic.Label();
          this.getChildControl("top-info").add(control, {
            row: this.self().TOP_GRID.GROUP_ID,
            column: 1
          });
          break;
        }
        case "institution":
          this.getChildControl("middle-info").add(new qx.ui.basic.Label("Institution"), {
            row: this.self().MIDDLE_GRID.INSTITUTION,
            column: 0
          });
          control = new qx.ui.basic.Label();
          this.getChildControl("middle-info").add(control, {
            row: this.self().MIDDLE_GRID.INSTITUTION,
            column: 1
          });
          break;
        case "address":
          this.getChildControl("middle-info").add(new qx.ui.basic.Label("Address"), {
            row: this.self().MIDDLE_GRID.ADDRESS,
            column: 0
          });
          control = new qx.ui.basic.Label();
          this.getChildControl("middle-info").add(control, {
            row: this.self().MIDDLE_GRID.ADDRESS,
            column: 1
          });
          break;
        case "city":
          this.getChildControl("middle-info").add(new qx.ui.basic.Label("City"), {
            row: this.self().MIDDLE_GRID.CITY,
            column: 0
          });
          control = new qx.ui.basic.Label();
          this.getChildControl("middle-info").add(control, {
            row: this.self().MIDDLE_GRID.CITY,
            column: 1
          });
          break;
        case "state":
          this.getChildControl("middle-info").add(new qx.ui.basic.Label("State"), {
            row: this.self().MIDDLE_GRID.STATE,
            column: 0
          });
          control = new qx.ui.basic.Label();
          this.getChildControl("middle-info").add(control, {
            row: this.self().MIDDLE_GRID.STATE,
            column: 1
          });
          break;
        case "country":
          this.getChildControl("middle-info").add(new qx.ui.basic.Label("Country"), {
            row: this.self().MIDDLE_GRID.COUNTRY,
            column: 0
          });
          control = new qx.ui.basic.Label();
          this.getChildControl("middle-info").add(control, {
            row: this.self().MIDDLE_GRID.COUNTRY,
            column: 1
          });
          break;
        case "postal-code":
          this.getChildControl("middle-info").add(new qx.ui.basic.Label("Postal Code"), {
            row: this.self().MIDDLE_GRID.POSTAL_CODE,
            column: 0
          });
          control = new qx.ui.basic.Label();
          this.getChildControl("middle-info").add(control, {
            row: this.self().MIDDLE_GRID.POSTAL_CODE,
            column: 1
          });
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
            // curate data
            userData["groupId"] = userGroupId;
            userData["userId"] = -1; // fix this
            userData["userName"] = "userName"; // fix this
            const user = new osparc.data.model.User(userData);
            user.setContactData(userData);
            // remove the displayed properties from the contact info
            Object.keys(qx.util.PropertyUtil.getProperties(osparc.data.model.User)).forEach(prop => delete userData[prop]);
            this.__remainingUserData = userData;
            this.setUser(user);
          }
        })
        .catch(err => {
          console.error(err);
          this.close();
        });
    },

    __applyUser: function(user) {
      this.setCaption(user.getUserName());

      // top grid
      this.getChildControl("userName").setValue(user.getUserName());
      this.getChildControl("fullname").setValue([user.getFirstName(), user.getLastName()].filter(Boolean).join(" "));
      this.getChildControl("email").setValue(user.getEmail());
      this.getChildControl("phone").setValue(user.getPhone() || "-");
      this.getChildControl("user-id").setValue(String(user.getUserId()));
      this.getChildControl("group-id").setValue(String(user.getGroupId()));

      this.getChildControl("thumbnail").setSource(user.createThumbnail(this.self().THUMBNAIL_SIZE));

      // middle grid
      this.getChildControl("institution").setValue(user.getInstitution() || "-");
      this.getChildControl("address").setValue(user.getAddress() || "-");
      this.getChildControl("city").setValue(user.getCity() || "-");
      this.getChildControl("state").setValue(user.getState() || "-");
      this.getChildControl("country").setValue(user.getCountry() || "-");
      this.getChildControl("postal-code").setValue(user.getPostalCode() || "-");

      /*
      const divId = this.getUserGroupId() + "_user_details";
      const htmlEmbed = osparc.wrapper.JsonFormatter.getInstance().createContainer(divId);
      setTimeout(() => {
        osparc.wrapper.JsonFormatter.getInstance().setJson(this.__remainingUserData, divId);
      }, 100);
      const container = new qx.ui.container.Scroll();
      container.add(htmlEmbed);
      this.add(container, {
        flex: 1
      });
      */
      const jsonViewer = new osparc.widget.JsonFormatterWidget();
      jsonViewer.set({
        allowGrowX: true,
        allowGrowY: true,
        width: null,
        height: null
      });
      const scroll = new qx.ui.container.Scroll();
      scroll.add(jsonViewer, { flex: 1 });
      this.add(scroll, { flex: 1 });
      jsonViewer.setJson(this.__remainingUserData);
    },
  }
});
