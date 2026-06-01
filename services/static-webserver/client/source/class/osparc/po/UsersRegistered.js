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

qx.Class.define("osparc.po.UsersRegistered", {
  extend: osparc.po.BaseView,

  statics: {
    COLUMNS: {
      NAME: 0,
      USERNAME: 1,
      EMAIL: 2,
      DATE: 3,
      INFO: 4,
    },
  },

  members: {
    __currentFilterText: "",
    __registeredUsers: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "header-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
            alignY: "middle"
          }));
          this._add(control);
          break;
        case "reload-button":
          control = new qx.ui.form.Button(this.tr("Reload")).set({
            allowGrowX: false,
          });
          control.addListener("execute", () => this.__reload());
          this.getChildControl("header-layout").add(control);
          break;
        case "intro-text":
          control = new qx.ui.basic.Label(this.tr("List of fully registered users:")).set({
            font: "text-14",
            textColor: "text",
            allowGrowX: true
          });
          this.getChildControl("header-layout").add(control);
          break;
        case "loading-spinner":
          control = new qx.ui.basic.Image("@FontAwesome5Solid/circle-notch/26").set({
            padding: 6
          });
          control.getContentElement().addClass("rotate");
          this._add(control);
          break;
        case "filter-users": {
          const filterGroupId = "registeredUsersLayout";
          control = new osparc.filter.TextFilter("text", filterGroupId).set({
            minWidth: 300,
          });
          control.getChildControl("textfield").setPlaceholder(this.tr("Filter by Name, Username or Email"));
          const msgName = osparc.utils.Utils.capitalize(filterGroupId, "filter");
          qx.event.message.Bus.getInstance().subscribe(msgName, this.__onFilterChange, this);
          this._add(control);
          break;
        }
        case "registered-users-container":
          control = new qx.ui.container.Scroll();
          this._add(control, {
            flex: 1
          });
          break;
        case "registered-users-layout": {
          const grid = new qx.ui.layout.Grid(15, 5);
          control = new qx.ui.container.Composite(grid);
          this.getChildControl("registered-users-container").add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    _buildLayout: function() {
      this.getChildControl("reload-button");
      this.getChildControl("intro-text");
      this.getChildControl("loading-spinner");
      this.__populateRegisteredUsersLayout();
    },

    __addHeader: function() {
      const layout = this.getChildControl("registered-users-layout");

      layout.add(new qx.ui.basic.Label(this.tr("Name")).set({
        font: "text-14"
      }), {
        row: 0,
        column: this.self().COLUMNS.NAME,
      });

      layout.add(new qx.ui.basic.Label(this.tr("Username")).set({
        font: "text-14"
      }), {
        row: 0,
        column: this.self().COLUMNS.USERNAME,
      });

      layout.add(new qx.ui.basic.Label(this.tr("Email")).set({
        font: "text-14"
      }), {
        row: 0,
        column: this.self().COLUMNS.EMAIL,
      });

      layout.add(new qx.ui.basic.Label(this.tr("Reviewed At")).set({
        font: "text-14"
      }), {
        row: 0,
        column: this.self().COLUMNS.DATE,
      });

      layout.add(new qx.ui.basic.Label(this.tr("Info")).set({
        font: "text-14"
      }), {
        row: 0,
        column: this.self().COLUMNS.INFO,
      });
    },

    __addRows: function(users) {
      const layout = this.getChildControl("registered-users-layout");
      const grid = layout.getLayout();

      let row = 1;
      users.forEach(user => {
        grid.setRowAlign(row, "left", "middle");

        const fullName = (user.firstName || "") + " " + (user.lastName || "");
        const fullNameLabel = new qx.ui.basic.Label(fullName.trim() || "-").set({
          selectable: true,
        });
        layout.add(fullNameLabel, {
          row,
          column: this.self().COLUMNS.NAME,
        });

        const usernameLabel = new qx.ui.basic.Label(user.userName || "-").set({
          selectable: true,
        });
        layout.add(usernameLabel, {
          row,
          column: this.self().COLUMNS.USERNAME,
        });

        const emailLabel = new qx.ui.basic.Label(user.email || "-").set({
          selectable: true,
        });
        layout.add(emailLabel, {
          row,
          column: this.self().COLUMNS.EMAIL,
        });

        const dateData = user.accountRequestReviewedAt;
        const date = dateData ? osparc.utils.Utils.formatDateAndTime(new Date(dateData)) : "-";
        layout.add(new qx.ui.basic.Label(date), {
          row,
          column: this.self().COLUMNS.DATE,
        });

        const infoButton = osparc.po.UsersPending.createInfoButton(user);
        layout.add(infoButton, {
          row,
          column: this.self().COLUMNS.INFO,
        });

        row++;
      });
    },

    __populateRegisteredUsersLayout: function() {
      this.getChildControl("loading-spinner").show();
      this.getChildControl("filter-users").exclude();

      const params = {
        url: {
          registered: "true",
        }
      };
      osparc.data.Resources.getInstance().getAllPages("poUsers", params, "getRegisteredUsers")
        .then(users => {
          this.getChildControl("filter-users").show();
          const sortByDate = (a, b) => {
            const dateA = a.accountRequestReviewedAt ? new Date(a.accountRequestReviewedAt) : new Date(0);
            const dateB = b.accountRequestReviewedAt ? new Date(b.accountRequestReviewedAt) : new Date(0);
            return dateB - dateA;
          };
          users.sort(sortByDate);
          this.__registeredUsers = users;
          this.__renderRegisteredUsers();
        })
        .catch(err => osparc.FlashMessenger.logError(err))
        .finally(() => this.getChildControl("loading-spinner").exclude());
    },

    __reload: function() {
      this.getChildControl("registered-users-layout").removeAll();
      this.__populateRegisteredUsersLayout();
    },

    __onFilterChange: function(msg) {
      const data = msg ? msg.getData() : null;
      this.__currentFilterText = data && data.text ? data.text : "";
      this.__renderRegisteredUsers();
    },

    __filterRegisteredUsers: function() {
      if (!this.__registeredUsers) {
        return [];
      }

      const text = this.__currentFilterText.trim();
      if (!text || text.length < 2) {
        return this.__registeredUsers;
      }

      const query = text.toLowerCase();
      return this.__registeredUsers.filter(user => {
        const fullName = `${user.firstName || ""} ${user.lastName || ""}`.trim().toLowerCase();
        const email = (user.email || "").toLowerCase();
        const username = (user.userName || "").toLowerCase();
        return [fullName, email, username].some(value => value.includes(query));
      });
    },

    __renderRegisteredUsers: function() {
      const layout = this.getChildControl("registered-users-layout");
      layout.removeAll();
      this.__addHeader();
      this.__addRows(this.__filterRegisteredUsers());
    },
  }
});
