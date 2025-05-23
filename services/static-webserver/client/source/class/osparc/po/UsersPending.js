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

qx.Class.define("osparc.po.UsersPending", {
  extend: osparc.po.BaseView,

  statics: {
    createApproveButton: function(email) {
      const button = new osparc.ui.form.FetchButton(qx.locale.Manager.tr("Approve"));
      button.addListener("execute", () => {
        button.setFetching(true);
        const params = {
          data: {
            email,
          },
        };
        osparc.data.Resources.fetch("poUsers", "approveUser", params)
          .then(() => {
            osparc.FlashMessenger.logAs(qx.locale.Manager.tr("User approved"), "INFO");
          })
          .catch(err => osparc.FlashMessenger.logError(err))
          .finally(() => button.setFetching(false));
      });
      return button;
    },

    createRejectButton: function(email) {
      const button = new osparc.ui.form.FetchButton(qx.locale.Manager.tr("Reject"));
      button.addListener("execute", () => {
        button.setFetching(true);
        const params = {
          data: {
            email,
          },
        };
        osparc.data.Resources.fetch("poUsers", "rejectUser", params)
          .then(() => {
            osparc.FlashMessenger.logAs(qx.locale.Manager.tr("User denied"), "INFO");
          })
          .catch(err => osparc.FlashMessenger.logError(err))
          .finally(() => button.setFetching(false));
      });
      return button;
    },

    createResendEmailButton: function(email) {
      const button = new osparc.ui.form.FetchButton(qx.locale.Manager.tr("Resend Email"));
      button.addListener("execute", () => {
        button.setFetching(true);
        const params = {
          data: {
            email,
          },
        };
        osparc.data.Resources.fetch("poUsers", "resendConfirmationEmail", params)
          .then(() => {
            osparc.FlashMessenger.logAs(qx.locale.Manager.tr("Email sent"), "INFO");
          })
          .catch(err => osparc.FlashMessenger.logError(err))
          .finally(() => button.setFetching(false));
      });
      return button;
    },

    createInfoButton: function(infoMetadata) {
      const infoButton = new qx.ui.form.Button(null, "@MaterialIcons/info_outline/16");
      infoButton.addListener("execute", () => {
        const container = new qx.ui.container.Scroll();
        container.add(new osparc.ui.basic.JsonTreeWidget(infoMetadata, "pendingUserInfo"));
        osparc.ui.window.Window.popUpInWindow(container, qx.locale.Manager.tr("User Info"));
      });
      return infoButton;
    },
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "pending-users-container":
          control = new qx.ui.container.Scroll();
          this._add(control, {
            flex: 1
          });
          break;
        case "pending-users-layout": {
          const grid = new qx.ui.layout.Grid(15, 5);
          control = new qx.ui.container.Composite(grid);
          this.getChildControl("pending-users-container").add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    _buildLayout: function() {
      this.getChildControl("pending-users-container");

      this.__populatePendingUsersLayout();
    },

    __addHeader: function() {
      const pendingUsersLayout = this.getChildControl("pending-users-layout");

      pendingUsersLayout.add(new qx.ui.basic.Label(this.tr("Name")).set({
        font: "text-14"
      }), {
        row: 0,
        column: 0,
      });

      pendingUsersLayout.add(new qx.ui.basic.Label(this.tr("Email")).set({
        font: "text-14"
      }), {
        row: 0,
        column: 1,
      });

      pendingUsersLayout.add(new qx.ui.basic.Label(this.tr("Date")).set({
        font: "text-14"
      }), {
        row: 0,
        column: 2,
      });

      pendingUsersLayout.add(new qx.ui.basic.Label(this.tr("Info")).set({
        font: "text-14"
      }), {
        row: 0,
        column: 3,
      });

      pendingUsersLayout.add(new qx.ui.basic.Label(this.tr("Status")).set({
        font: "text-14"
      }), {
        row: 0,
        column: 4,
      });

      pendingUsersLayout.add(new qx.ui.basic.Label(this.tr("Action")).set({
        font: "text-14"
      }), {
        row: 0,
        column: 5,
      });
    },

    __addRows: function(pendingUsers) {
      const pendingUsersLayout = this.getChildControl("pending-users-layout");

      let row = 1;
      pendingUsers.forEach(pendingUser => {
        pendingUsersLayout.add(new qx.ui.basic.Label(pendingUser.name), {
          row,
          column: 0,
        });
        pendingUsersLayout.add(new qx.ui.basic.Label(pendingUser.email), {
          row,
          column: 1,
        });
        pendingUsersLayout.add(new qx.ui.basic.Label(osparc.utils.Utils.formatDateAndTime(new Date(pendingUser.date))), {
          row,
          column: 2,
        });
        const infoButton = this.self().createInfoButton(pendingUser.info);
        pendingUsersLayout.add(infoButton, {
          row,
          column: 3,
        });
        pendingUsersLayout.add(new qx.ui.basic.Label(pendingUser.status.toLowerCase()), {
          row,
          column: 4,
        });
        const buttonsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
        pendingUsersLayout.add(buttonsLayout, {
          row,
          column: 5,
        });

        switch (pendingUser.status) {
          case "PENDING": {
            const approveButton = this.self().createApproveButton(pendingUser.email);
            buttonsLayout.add(approveButton);
            const rejectButton = this.self().createRejectButton(pendingUser.email);
            buttonsLayout.add(rejectButton);
            break;
          }
          case "REJECTED": {
            const approveButton = this.self().createApproveButton(pendingUser.email);
            buttonsLayout.add(approveButton);
            break;
          }
          case "APPROVED": {
            /*
            const resendEmailButton = this.self().createResendEmailButton(pendingUser.email);
            buttonsLayout.add(resendEmailButton);
            */
            const rejectButton = this.self().createRejectButton(pendingUser.email);
            buttonsLayout.add(rejectButton);
            break;
          }
        }
        row++;
      });
    },

    __populatePendingUsersLayout: function() {
      Promise.all([
        osparc.data.Resources.fetch("poUsers", "getPendingUsers"),
        osparc.data.Resources.fetch("poUsers", "getReviewedUsers")
      ])
        .then(resps => {
          const pendingUsers = resps[0]["data"];
          const reviewedUsers = resps[1]["data"];
          const pendingUsersLayout = this.getChildControl("pending-users-layout");
          pendingUsersLayout.removeAll();
          this.__addHeader();
          this.__addRows(pendingUsers.concat(reviewedUsers));
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    }
  }
});
