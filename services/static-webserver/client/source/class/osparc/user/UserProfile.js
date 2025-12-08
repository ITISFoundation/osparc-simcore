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

qx.Class.define("osparc.user.UserProfile", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));
  },

  statics: {
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

    createLabel: function() {
      return new qx.ui.basic.Label().set({
        selectable: true,
      });
    },
  },

  properties: {
    user: {
      check: "osparc.data.model.User",
      init: null,
      nullable: true,
      event: "changeUser",
      apply: "__applyUser",
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "top-info": {
          const grid = new qx.ui.layout.Grid(10, 6);
          grid.setColumnWidth(0, 80);
          grid.setColumnFlex(1, 1);
          grid.setColumnAlign(0, "right", "middle");
          control = new qx.ui.container.Composite(grid);
          this._add(control);
          break;
        }
        case "middle-info": {
          const grid = new qx.ui.layout.Grid(10, 6);
          grid.setColumnWidth(0, 80);
          grid.setColumnFlex(1, 1);
          grid.setColumnAlign(0, "right", "middle");
          control = new qx.ui.container.Composite(grid);
          this._add(control);
          break;
        }
        case "userName": {
          this.getChildControl("top-info").add(new qx.ui.basic.Label("UserName"), {
            row: this.self().TOP_GRID.USERNAME,
            column: 0
          });
          control = this.self().createLabel();
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
          control = this.self().createLabel();
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
          control = this.self().createLabel();
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
          control = this.self().createLabel();
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
          control = this.self().createLabel();
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
          control = this.self().createLabel();
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
          control = this.self().createLabel();
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
          control = this.self().createLabel();
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
          control = this.self().createLabel();
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
          control = this.self().createLabel();
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
          control = this.self().createLabel();
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
          control = this.self().createLabel();
          this.getChildControl("middle-info").add(control, {
            row: this.self().MIDDLE_GRID.POSTAL_CODE,
            column: 1
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyUser: function(user) {
      if (!user) {
        return;
      }

      // top grid
      this.getChildControl("userName").setValue(user.getUserName());
      this.getChildControl("fullname").setValue([user.getFirstName(), user.getLastName()].filter(Boolean).join(" "));
      this.getChildControl("email").setValue(user.getEmail());
      this.getChildControl("phone").setValue(user.getPhone() || "-");
      this.getChildControl("user-id").setValue(String(user.getUserId()));
      this.getChildControl("group-id").setValue(String(user.getGroupId()));

      // middle grid
      this.getChildControl("institution").setValue(user.getInstitution() || "-");
      this.getChildControl("address").setValue(user.getAddress() || "-");
      this.getChildControl("city").setValue(user.getCity() || "-");
      this.getChildControl("state").setValue(user.getState() || "-");
      this.getChildControl("country").setValue(user.getCountry() || "-");
      this.getChildControl("postal-code").setValue(user.getPostalCode() || "-");
    },
  }
});
