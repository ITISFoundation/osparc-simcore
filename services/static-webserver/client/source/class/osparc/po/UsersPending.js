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
    createInvitationForm: function(withEmail = false) {
      const form = new qx.ui.form.Form();

      if (withEmail) {
        const userEmail = new qx.ui.form.TextField().set({
          required: true,
          placeholder: "new.user@email.address"
        });
        form.add(userEmail, qx.locale.Manager.tr("User Email"), null, "email");
      }

      const extraCreditsInUsd = new qx.ui.form.Spinner().set({
        minimum: 0,
        maximum: 1000,
        value: osparc.product.Utils.getDefaultWelcomeCredits(),
      });
      form.add(extraCreditsInUsd, qx.locale.Manager.tr("Welcome Credits (USD)"), null, "credits");

      const withExpiration = new qx.ui.form.CheckBox().set({
        value: false
      });
      form.add(withExpiration, qx.locale.Manager.tr("With expiration"), null, "withExpiration");

      const trialDays = new qx.ui.form.Spinner().set({
        minimum: 1,
        maximum: 1000,
        value: 1
      });
      withExpiration.bind("value", trialDays, "visibility", {
        converter: val => val ? "visible" : "excluded"
      });
      form.add(trialDays, qx.locale.Manager.tr("Trial Days"), null, "trialDays");

      return form;
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
      const infoButton = new qx.ui.form.Button(null, "@MaterialIcons/info_outline/14");
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
        case "reload-button":
          control = new qx.ui.form.Button(this.tr("Reload")).set({
            allowGrowX: false,
          });
          control.addListener("execute", () => this.__reload());
          this._add(control);
          break;
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
      this.getChildControl("reload-button");
      this.getChildControl("pending-users-container");
      this.__addHeader();
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

      pendingUsersLayout.add(new qx.ui.basic.Label(this.tr("Status")).set({
        font: "text-14"
      }), {
        row: 0,
        column: 3,
      });
    },

    __addRows: function(pendingUsers) {
      const pendingUsersLayout = this.getChildControl("pending-users-layout");
      const grid = pendingUsersLayout.getLayout();

      let row = 1;
      pendingUsers.forEach(pendingUser => {
        grid.setRowAlign(row, "left", "middle");

        pendingUsersLayout.add(new qx.ui.basic.Label(pendingUser.firstName + " " + pendingUser.lastName), {
          row,
          column: 0,
        });

        pendingUsersLayout.add(new qx.ui.basic.Label(pendingUser.email), {
          row,
          column: 1,
        });

        let date = null;
        switch (pendingUser.accountRequestStatus) {
          case "PENDING":
            date = pendingUser.preRegistrationRequestedAt ? osparc.utils.Utils.formatDateAndTime(new Date(pendingUser.preRegistrationRequestedAt)) : "-";
            break;
          default:
            date = pendingUser.accountRequestReviewedAt ? osparc.utils.Utils.formatDateAndTime(new Date(pendingUser.accountRequestReviewedAt)) : "-";
            break;
        }
        pendingUsersLayout.add(new qx.ui.basic.Label(date), {
          row,
          column: 2,
        });

        const statusChip = new osparc.ui.basic.Chip().set({
          label: pendingUser.accountRequestStatus.toLowerCase(),
        });
        statusChip.getChildControl("label").set({
          font: "text-12",
        });
        pendingUsersLayout.add(statusChip, {
          row,
          column: 3,
        });

        const infoButton = this.self().createInfoButton(pendingUser);
        pendingUsersLayout.add(infoButton, {
          row,
          column: 4,
        });

        const buttonsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
        pendingUsersLayout.add(buttonsLayout, {
          row,
          column: 5,
        });
        switch (pendingUser.accountRequestStatus) {
          case "PENDING": {
            statusChip.setStatusColor(osparc.ui.basic.Chip.STATUS.WARNING);
            const approveButton = this.__createApproveButton(pendingUser.email);
            buttonsLayout.add(approveButton);
            const rejectButton = this.__createRejectButton(pendingUser.email);
            buttonsLayout.add(rejectButton);
            break;
          }
          case "REJECTED": {
            statusChip.setStatusColor(osparc.ui.basic.Chip.STATUS.ERROR);
            const approveButton = this.__createApproveButton(pendingUser.email);
            approveButton.setEnabled(false); // avoid changing decision for now
            buttonsLayout.add(approveButton);
            break;
          }
          case "APPROVED": {
            statusChip.setStatusColor(osparc.ui.basic.Chip.STATUS.SUCCESS);
            const resendEmailButton = this.self().createResendEmailButton(pendingUser.email);
            resendEmailButton.setEnabled(false);
            buttonsLayout.add(resendEmailButton);
            const rejectButton = this.__createRejectButton(pendingUser.email);
            rejectButton.setEnabled(false); // avoid changing decision for now
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
          const pendingUsers = resps[0];
          const reviewedUsers = resps[1];
          const sortByDate = (a, b) => {
            let dateA = new Date(0); // default to epoch if no date is available
            if (a.accountRequestStatus === "PENDING" && a.preRegistrationRequestedAt) {
              dateA = new Date(a.preRegistrationRequestedAt);
            } else if (a.accountRequestReviewedAt) {
              dateA = new Date(a.accountRequestReviewedAt);
            }
            let dateB = new Date(0); // default to epoch if no date is available
            if (b.accountRequestStatus === "PENDING" && b.preRegistrationRequestedAt) {
              dateB = new Date(b.preRegistrationRequestedAt);
            } else if (b.accountRequestReviewedAt) {
              dateB = new Date(b.accountRequestReviewedAt);
            }
            return dateB - dateA; // sort by most recent first
          };
          pendingUsers.sort(sortByDate);
          reviewedUsers.sort(sortByDate);
          this.__addRows(pendingUsers.concat(reviewedUsers));
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    __reload: function() {
      this.getChildControl("pending-users-layout").removeAll();
      this.__addHeader();
      this.__populatePendingUsersLayout();
    },

    __createApproveButton: function(email) {
      const button = new qx.ui.form.Button(qx.locale.Manager.tr("Approve"));
      button.addListener("execute", () => {
        const form = this.self().createInvitationForm(false);
        const approveBtn = new osparc.ui.form.FetchButton(qx.locale.Manager.tr("Approve"));
        approveBtn.set({
          appearance: "form-button"
        });
        form.addButton(approveBtn);
        const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
        const invitationForm = new qx.ui.form.renderer.Single(form);
        layout.add(invitationForm);
        const win = osparc.ui.window.Window.popUpInWindow(layout, email, 350, 150).set({
          clickAwayClose: false,
          resizable: false,
          showClose: true
        });
        win.open();
        approveBtn.addListener("execute", () => {
          if (osparc.data.Permissions.getInstance().canDo("user.invitation.generate", true)) {
            if (form.validate()) {
              const extraCreditsInUsd = form.getItems()["credits"].getValue();
              let trialAccountDays = 0;
              if (form.getItems()["withExpiration"].getValue()) {
                trialAccountDays = form.getItems()["trialDays"].getValue();
              }

              let msg = `Are you sure you want to approve ${email}`;
              if (extraCreditsInUsd) {
                msg += ` with ${extraCreditsInUsd}$ worth credits`;
              }
              if (trialAccountDays > 0) {
                msg += ` and ${trialAccountDays} days of trial`;
              }
              msg += "?";
              const confWin = new osparc.ui.window.Confirmation(msg).set({
                caption: "Approve User",
                confirmText: "Approve",
                confirmAction: "create"
              });
              confWin.center();
              confWin.open();
              confWin.addListener("close", () => {
                if (confWin.getConfirmed()) {
                  approveBtn.setFetching(true);
                  this.__approveUser(email, form)
                    .then(() => {
                      osparc.FlashMessenger.logAs("User approved", "INFO");
                      this.__reload();
                    })
                    .catch(err => osparc.FlashMessenger.logError(err))
                    .finally(() => {
                      approveBtn.setFetching(false);
                      win.close();
                    });
                }
              });
            }
          }
        });
      });
      return button;
    },

    __createRejectButton: function(email) {
      const button = new osparc.ui.form.FetchButton("Reject");
      button.addListener("execute", () => {
        const msg = `Are you sure you want to reject ${email}.<br>The operation cannot be reverted`;
        const win = new osparc.ui.window.Confirmation(msg).set({
          caption: "Reject User",
          confirmText: "Reject",
          confirmAction: "delete",
        });
        win.center();
        win.open();
        win.addListener("close", () => {
          if (win.getConfirmed()) {
            button.setFetching(true);
            this.__rejectUser(email)
              .then(() => {
                osparc.FlashMessenger.logAs(qx.locale.Manager.tr("User denied"), "INFO");
                this.__reload();
              })
              .catch(err => osparc.FlashMessenger.logError(err))
              .finally(() => button.setFetching(false));
          }
        });
      });
      return button;
    },

    __approveUser: function(email, form) {
      const params = {
        data: {
          email,
        },
      };
      params.data["invitation"] = {};
      const extraCreditsInUsd = form.getItems()["credits"].getValue();
      if (extraCreditsInUsd > 0) {
        params.data["invitation"]["extraCreditsInUsd"] = extraCreditsInUsd;
      }
      if (form.getItems()["withExpiration"].getValue()) {
        params.data["invitation"]["trialAccountDays"] = form.getItems()["trialDays"].getValue();
      }
      return osparc.data.Resources.fetch("poUsers", "approveUser", params);
    },

    __rejectUser: function(email) {
      const params = {
        data: {
          email,
        },
      };
      return osparc.data.Resources.fetch("poUsers", "rejectUser", params);
    },
  }
});
