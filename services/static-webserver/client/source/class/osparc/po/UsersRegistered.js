/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2026 IT'IS Foundation, https://itis.swiss

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

    PAGE_LIMIT: 20,
  },

  members: {
    __currentOrderBy: null,
    __registeredUsers: null,
    __currentOffset: 0,
    __totalUsers: 0,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "header-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
            alignY: "middle"
          }));
          this._add(control);
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
        case "registered-users-container":
          control = new qx.ui.container.Scroll();
          this._add(control, {
            flex: 1
          });
          break;
        case "registered-users-layout": {
          const grid = new qx.ui.layout.Grid(20, 5);
          control = new qx.ui.container.Composite(grid);
          this.getChildControl("registered-users-container").add(control);
          break;
        }
        case "pagination-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(8).set({
            alignY: "middle",
            alignX: "left"
          })).set({
            marginTop: 5,
          });
          this._add(control);
          break;
        case "prev-page-button":
          control = new qx.ui.form.Button(null, "@MaterialIcons/chevron_left/16").set({
            allowGrowX: false,
            enabled: false,
            toolTipText: this.tr("Previous page"),
          });
          control.addListener("execute", () => {
            this.__currentOffset = Math.max(0, this.__currentOffset - this.self().PAGE_LIMIT);
            this.__fetchPage();
          });
          this.getChildControl("pagination-layout").add(control);
          break;
        case "page-info-label":
          control = new qx.ui.basic.Label("").set({
            font: "text-13",
            textColor: "text",
          });
          this.getChildControl("pagination-layout").add(control);
          break;
        case "next-page-button":
          control = new qx.ui.form.Button(null, "@MaterialIcons/chevron_right/16").set({
            allowGrowX: false,
            enabled: false,
            toolTipText: this.tr("Next page"),
          });
          control.addListener("execute", () => {
            this.__currentOffset += this.self().PAGE_LIMIT;
            this.__fetchPage();
          });
          this.getChildControl("pagination-layout").add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    _buildLayout: function() {
      this.getChildControl("intro-text");
      this.getChildControl("loading-spinner");
      this.getChildControl("registered-users-container");
      this.getChildControl("pagination-layout");
      this.__currentOrderBy = "-accountRequestReviewedAt";
      this.addListenerOnce("appear", () => this.__fetchPage());
    },

    __createSortableHeader: function(label, fieldName) {
      const container = new qx.ui.container.Composite(new qx.ui.layout.HBox(4).set({
        alignY: "middle"
      }));
      container.set({
        cursor: "pointer",
      });
      const textLabel = new qx.ui.basic.Label(label).set({
        font: "text-14",
      });
      container.add(textLabel);
      const sortIcon = new qx.ui.basic.Label("").set({
        font: "text-12",
      });
      container.add(sortIcon);
      // Update icon based on current sort
      const currentField = this.__currentOrderBy.replace(/^-/, "");
      const isDesc = this.__currentOrderBy.startsWith("-");
      if (currentField === fieldName) {
        sortIcon.setValue(isDesc ? "\u25BC" : "\u25B2");
      }
      container.addListener("tap", () => {
        const curField = this.__currentOrderBy.replace(/^-/, "");
        const curDesc = this.__currentOrderBy.startsWith("-");
        if (curField === fieldName) {
          // Toggle direction
          this.__currentOrderBy = curDesc ? fieldName : "-" + fieldName;
        } else {
          // Default to ascending for new field
          this.__currentOrderBy = fieldName;
        }
        this.__reload();
      });
      return container;
    },

    __addHeader: function() {
      const layout = this.getChildControl("registered-users-layout");

      layout.add(new qx.ui.basic.Label(this.tr("Name")).set({
        font: "text-14"
      }), {
        row: 0,
        column: this.self().COLUMNS.NAME,
      });

      layout.add(this.__createSortableHeader(this.tr("Username"), "userName"), {
        row: 0,
        column: this.self().COLUMNS.USERNAME,
      });

      layout.add(this.__createSortableHeader(this.tr("Email"), "email"), {
        row: 0,
        column: this.self().COLUMNS.EMAIL,
      });

      layout.add(this.__createSortableHeader(this.tr("Reviewed At"), "accountRequestReviewedAt"), {
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

    __fetchPage: function() {
      this.getChildControl("loading-spinner").show();

      const params = {
        url: {
          offset: this.__currentOffset,
          limit: this.self().PAGE_LIMIT,
          orderBy: this.__currentOrderBy,
        }
      };
      const options = {
        resolveWResponse: true,
      };
      osparc.data.Resources.fetch("poUsers", "getRegisteredUsers", params, options)
        .then(resp => {
          const meta = ("_meta" in resp["data"]) ? resp["data"]["_meta"] : resp["_meta"];
          const data = ("_meta" in resp["data"]) ? resp["data"]["data"] : resp["data"];
          this.__totalUsers = meta.total;
          this.__registeredUsers = data;
          this.__updatePaginationControls();
          this.__renderRegisteredUsers();
        })
        .catch(err => osparc.FlashMessenger.logError(err))
        .finally(() => this.getChildControl("loading-spinner").exclude());
    },

    __updatePaginationControls: function() {
      this.getChildControl("prev-page-button").setEnabled(this.__currentOffset > 0);
      const currentPage = Math.floor(this.__currentOffset / this.self().PAGE_LIMIT) + 1;
      const totalPages = Math.ceil(this.__totalUsers / this.self().PAGE_LIMIT) || 1;
      this.getChildControl("page-info-label").setValue(
        this.tr("Page %1/%2 (%3 users)", currentPage, totalPages, this.__totalUsers)
      );
      this.getChildControl("next-page-button").setEnabled(this.__currentOffset + this.self().PAGE_LIMIT < this.__totalUsers);
    },

    __reload: function() {
      this.__currentOffset = 0;
      this.getChildControl("registered-users-layout").removeAll();
      this.__fetchPage();
    },

    __renderRegisteredUsers: function() {
      const layout = this.getChildControl("registered-users-layout");
      layout.removeAll();
      this.__addHeader();
      this.__addRows(this.__registeredUsers || []);
    },
  }
});
