/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo-Valero (pcrespov)
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.po.Users", {
  extend: osparc.po.BaseView,

  statics: {
    GRID_POS: {
      USERNAME: 0,
      EMAIL: 1,
      DATE: 2,
      ACCOUNT_REQUEST_STATUS: 3,
      STATUS: 4,
      INFO: 5,
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "search-users":
          control = this.__searchUsers();
          this._add(control);
          break;
        case "finding-status":
          control = new qx.ui.basic.Label();
          this._add(control);
          break;
        case "found-users-container":
          control = new qx.ui.container.Scroll();
          this._add(control, {
            flex: 1
          });
          break;
        case "found-users-layout": {
          const grid = new qx.ui.layout.Grid(15, 5);
          control = new qx.ui.container.Composite(grid);
          this.getChildControl("found-users-container").add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    _buildLayout: function() {
      this.getChildControl("search-users");
      this.getChildControl("finding-status");
      this.getChildControl("found-users-container");
    },

    __searchUsers: function() {
      const usersGroupBox = osparc.po.BaseView.createGroupBox(this.tr("Search"));

      const searchUsersForm = this.__searchUsersForm();
      const form = new qx.ui.form.renderer.Single(searchUsersForm);
      usersGroupBox.add(form);

      return usersGroupBox;
    },

    __searchUsersForm: function() {
      const form = new qx.ui.form.Form();

      const userEmail = new qx.ui.form.TextField().set({
        required: true,
        placeholder: this.tr("user@email.address or user@*")
      });
      form.add(userEmail, this.tr("Email"));

      const searchBtn = new osparc.ui.form.FetchButton(this.tr("Search"));
      searchBtn.set({
        appearance: "form-button"
      });
      const commandEsc = new qx.ui.command.Command("Enter");
      searchBtn.setCommand(commandEsc);
      searchBtn.addListener("execute", () => {
        if (!osparc.data.Permissions.getInstance().canDo("user.users.search", true)) {
          return;
        }
        if (form.validate()) {
          searchBtn.setFetching(true);
          const findingStatus = this.getChildControl("finding-status");
          findingStatus.setValue(this.tr("Searching users..."));
          const params = {
            url: {
              email: userEmail.getValue()
            }
          };
          osparc.data.Resources.fetch("poUsers", "searchByEmail", params)
            .then(data => {
              findingStatus.setValue(data.length + this.tr(" user(s) found"));
              this.__populateFoundUsersLayout(data);
            })
            .catch(err => {
              findingStatus.setValue(this.tr("Error searching users"));
              osparc.FlashMessenger.logError(err);
            })
            .finally(() => searchBtn.setFetching(false));
        }
      }, this);
      form.addButton(searchBtn);

      return form;
    },

    __createHeaderLabel: function(value) {
      const label = new qx.ui.basic.Label(value).set({
        font: "text-16",
        textColor: "text"
      });
      return label;
    },

    __addHeader: function() {
      const foundUsersLayout = this.getChildControl("found-users-layout");
      foundUsersLayout.add(this.__createHeaderLabel(this.tr("Username")), {
        row: 0,
        column: this.self().GRID_POS.USERNAME,
      });
      foundUsersLayout.add(this.__createHeaderLabel(this.tr("Email")), {
        row: 0,
        column: this.self().GRID_POS.EMAIL,
      });
      foundUsersLayout.add(this.__createHeaderLabel(this.tr("Date")), {
        row: 0,
        column: this.self().GRID_POS.DATE,
      });
      foundUsersLayout.add(this.__createHeaderLabel(this.tr("Request")), {
        row: 0,
        column: this.self().GRID_POS.ACCOUNT_REQUEST_STATUS,
      });
      foundUsersLayout.add(this.__createHeaderLabel(this.tr("Status")), {
        row: 0,
        column: this.self().GRID_POS.STATUS,
      });
    },

    __populateFoundUsersLayout: function(foundUsers) {
      const foundUsersLayout = this.getChildControl("found-users-layout");
      foundUsersLayout.removeAll();

      this.__addHeader();
      foundUsers.forEach((user, index) => {
        const row = index + 1;

        const userNameLabel = new qx.ui.basic.Label(user["username"]).set({
          selectable: true,
        });
        foundUsersLayout.add(userNameLabel, {
          row,
          column: this.self().GRID_POS.USERNAME,
        });

        const emailLabel = new qx.ui.basic.Label(user["email"]).set({
          selectable: true,
        });
        foundUsersLayout.add(emailLabel, {
          row,
          column: this.self().GRID_POS.EMAIL,
        });

        const dateData = user["preRegistrationCreated"] || user["accountRequestReviewedAt"];
        const date = dateData ? osparc.utils.Utils.formatDateAndTime(new Date(dateData)) : "-";
        const dateLabel = new qx.ui.basic.Label(date);
        foundUsersLayout.add(dateLabel, {
          row,
          column: this.self().GRID_POS.DATE,
        });

        const accountRequestStatusLabel = new qx.ui.basic.Label(user["accountRequestStatus"]);
        foundUsersLayout.add(accountRequestStatusLabel, {
          row,
          column: this.self().GRID_POS.ACCOUNT_REQUEST_STATUS,
        });

        const statusLabel = new qx.ui.basic.Label(user["status"]);
        foundUsersLayout.add(statusLabel, {
          row,
          column: this.self().GRID_POS.STATUS,
        });

        const infoButton = osparc.po.UsersPending.createInfoButton(user);
        foundUsersLayout.add(infoButton, {
          row,
          column: this.self().GRID_POS.INFO,
        });
      });
    },
  }
});
