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
        visibility: osparc.store.StaticInfo.isBillableProduct() ? "visible" : "excluded",
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
        container.add(new osparc.ui.basic.JsonTreeWidget(infoMetadata, "userInfo"));
        osparc.ui.window.Window.popUpInWindow(container, qx.locale.Manager.tr("User Info"));
      });
      return infoButton;
    },

    extractDate: function(pendingUser) {
      if (pendingUser.accountRequestStatus === "PENDING" && pendingUser.preRegistrationCreated) {
        return pendingUser.preRegistrationCreated;
      } else if (pendingUser.accountRequestReviewedAt) {
        return pendingUser.accountRequestReviewedAt;
      }
      return null;
    },
  },

  members: {
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
          control = new qx.ui.basic.Label(this.tr("List of pending users or approved/rejected, but not yet registered:")).set({
            font: "text-14",
            textColor: "text",
            allowGrowX: true
          });
          this.getChildControl("header-layout").add(control);
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
      this.getChildControl("intro-text");
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

        const fullNameLabel = new qx.ui.basic.Label(pendingUser.firstName + " " + pendingUser.lastName).set({
          selectable: true,
        });
        pendingUsersLayout.add(fullNameLabel, {
          row,
          column: 0,
        });

        const emailLabel = new qx.ui.basic.Label(pendingUser.email).set({
          selectable: true,
        });
        pendingUsersLayout.add(emailLabel, {
          row,
          column: 1,
        });

        const dateData = this.self().extractDate(pendingUser);
        const date = dateData ? osparc.utils.Utils.formatDateAndTime(new Date(dateData)) : "-";
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
            const dateDataA = this.self().extractDate(a);
            const dateA = dateDataA ? new Date(dateDataA) : new Date(0); // default to epoch if no date is available
            const dateDataB = this.self().extractDate(b);
            const dateB = dateDataB ? new Date(dateDataB) : new Date(0); // default to epoch if no date is available
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
      button.addListener("execute", () => this.__openApproveDialog(email));
      return button;
    },

    __createRejectButton: function(email) {
      const button = new qx.ui.form.Button(qx.locale.Manager.tr("Reject"));
      button.addListener("execute", () => this.__previewRejection(email));
      return button;
    },

    __openApproveDialog: function(email) {
      const form = this.self().createInvitationForm(false);
      const approveBtn = new qx.ui.form.Button(qx.locale.Manager.tr("Preview Approve")).set({
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
            const invitationData = {};
            const extraCreditsInUsd = form.getItems()["credits"].getValue();
            if (extraCreditsInUsd > 0) {
              invitationData["extraCreditsInUsd"] = extraCreditsInUsd;
            }
            if (form.getItems()["withExpiration"].getValue()) {
              invitationData["trialAccountDays"] = form.getItems()["trialDays"].getValue();
            }
            win.close();
            this.__previewApproval(email, invitationData);
          }
        }
      });
    },

    __previewApproval: function(email, invitationData) {
      const params = {
        data: {
          email,
          invitation: invitationData
        }
      };
      osparc.data.Resources.fetch("poUsers", "previewApproval", params)
        .then(data => {
          const invitationUrl = data["invitationUrl"];
          const messageContent = data["messageContent"];
          this.__openApprovalPreview(email, invitationUrl, messageContent);
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    __openApprovalPreview: function(email, invitationUrl, messageContent) {
      const previewApproval = new osparc.po.PreviewApprovalRejection();
      previewApproval.set({
        invitationUrl,
        email,
        subject: messageContent["subject"],
        bodyHtml: messageContent["bodyHtml"],
      });
      const win = osparc.ui.window.Window.popUpInWindow(previewApproval, qx.locale.Manager.tr("Preview email"), 700, 670);
      previewApproval.addListener("userApproved", () => {
        win.close();
        this.__reload();
      });
    },

    __previewRejection: function(email) {
      const params = {
        data: {
          email,
        }
      };
      osparc.data.Resources.fetch("poUsers", "previewRejection", params)
        .then(data => {
          const messageContent = data["messageContent"];
          this.__openRejectionPreview(email, messageContent);
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    __openRejectionPreview: function(email, messageContent) {
      const previewRejection = new osparc.po.PreviewApprovalRejection().set({
        actionMode: "reject",
      });
      previewRejection.getChildControl("invitation-url-container").exclude();
      previewRejection.set({
        email,
        subject: messageContent["subject"],
        bodyHtml: messageContent["bodyHtml"],
      });

      const win = osparc.ui.window.Window.popUpInWindow(previewRejection, qx.locale.Manager.tr("Preview email"), 700, 670);
      previewRejection.addListener("userRejected", () => {
        win.close();
        this.__reload();
      });
    },
  }
});
