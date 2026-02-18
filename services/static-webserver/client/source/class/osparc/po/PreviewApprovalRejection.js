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

qx.Class.define("osparc.po.PreviewApprovalRejection", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__buildLayout();
  },

  properties: {
    actionMode: {
      check: ["approve", "reject"],
      nullable: false,
      init: true,
      event: "changeActionMode",
    },

    email: {
      check: "String",
      nullable: false,
      init: null,
      apply: "__applyEmailAddress",
    },

    invitationUrl: {
      check: "String",
      nullable: false,
      init: null,
      apply: "__applyInvitationUrl",
    },

    subject: {
      check: "String",
      nullable: false,
      init: null,
      apply: "__applySubject",
    },

    bodyHtml: {
      check: "String",
      nullable: false,
      init: null,
      apply: "__applyBodyHtml",
    },
  },

  events: {
    "userApproved": "qx.event.type.Event",
    "userRejected": "qx.event.type.Event",
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "email-editor": {
          control = new osparc.po.EmailEditor();
          this._add(control, {
            flex: 1
          });
          break;
        }
        case "invitation-url-container": {
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
            alignY: "middle",
          }));
          this._add(control);
          break;
        }
        case "invitation-url": {
          control = new qx.ui.form.TextField().set({
            readOnly: true,
            allowGrowX: true,
          });
          this.getChildControl("invitation-url-container").add(control, {
            flex: 1
          });
          break;
        }
        case "copy-invitation-url-button": {
          control = new qx.ui.form.Button(null, "@FontAwesome5Solid/copy/12").set({
            allowGrowX: false,
            allowGrowY: true,
            toolTipText: this.tr("Copy Invitation URL"),
          });
          control.addListener("execute", () => {
            const invitationUrlField = this.getChildControl("invitation-url");
            osparc.utils.Utils.copyToClipboard(invitationUrlField.getValue());
          }, this);
          this.getChildControl("invitation-url-container").add(control);
          break;
        }
        case "button-bar": {
          const layout = new qx.ui.layout.HBox(10);
          layout.setAlignX("right");
          control = new qx.ui.container.Composite(layout).set({
            padding: 10
          });
          this._add(control);
          break;
        }
        case "approve-without-email-button":
          control = new osparc.ui.form.FetchButton(this.tr("Approve without Sending Email")).set({
            allowGrowX: false
          });
          control.addListener("execute", () => this.__approveWithoutEmail(), this);
          this.bind("actionMode", control, "visibility", {
            converter: val => val === "approve" ? "visible" : "excluded"
          });
          this.getChildControl("button-bar").add(control);
          break;
        case "approve-with-email-button":
          control = new osparc.ui.form.FetchButton(this.tr("Approve and Send")).set({
            appearance: "strong-button",
            allowGrowX: false
          });
          control.addListener("execute", () => this.__sendEmailClicked(), this);
          this.bind("actionMode", control, "visibility", {
            converter: val => val === "approve" ? "visible" : "excluded"
          });
          this.getChildControl("button-bar").add(control);
          break;
        case "reject-without-email-button":
          control = new osparc.ui.form.FetchButton(this.tr("Reject without Sending Email")).set({
            allowGrowX: false
          });
          control.addListener("execute", () => this.__rejectWithoutEmail(), this);
          this.bind("actionMode", control, "visibility", {
            converter: val => val === "reject" ? "visible" : "excluded"
          });
          this.getChildControl("button-bar").add(control);
          break;
        case "reject-with-email-button":
          control = new osparc.ui.form.FetchButton(this.tr("Reject and Send")).set({
            appearance: "danger-button",
            allowGrowX: false
          });
          control.addListener("execute", () => this.__sendEmailClicked(), this);
          this.bind("actionMode", control, "visibility", {
            converter: val => val === "reject" ? "visible" : "excluded"
          });
          this.getChildControl("button-bar").add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("email-editor");
      this.getChildControl("invitation-url");
      this.getChildControl("copy-invitation-url-button");
      this.getChildControl("approve-without-email-button");
      this.getChildControl("approve-with-email-button");
      this.getChildControl("reject-without-email-button");
      this.getChildControl("reject-with-email-button");
    },

    __applyEmailAddress: function(value) {
      const emailEditor = this.getChildControl("email-editor");
      const chip = emailEditor.addChip(value, value);
      chip.setEnabled(false);
      emailEditor.getChildControl("add-recipient-button").exclude();
    },

    __applyInvitationUrl: function(value) {
      const invitationUrlField = this.getChildControl("invitation-url");
      invitationUrlField.setValue(value);
    },

    __applySubject: function(value) {
      const emailEditor = this.getChildControl("email-editor");
      const subjectField = emailEditor.getChildControl("subject-field");
      subjectField.setValue(value);
    },

    __applyBodyHtml: function(value) {
      const emailEditor = this.getChildControl("email-editor");
      const emailContentEditor = emailEditor.getChildControl("email-content-editor-and-preview");
      emailContentEditor.setTemplateEmail(value);
    },

    __sendEmailClicked: function() {
      const emailEditor = this.getChildControl("email-editor");

      // make sure subject is not empty
      const subjectField = emailEditor.getChildControl("subject-field");
      if (!subjectField.getValue()) {
        osparc.FlashMessenger.logAs(this.tr("Please enter a subject"), "WARNING");
        return;
      }

      // if the user is not in the preview page, force them there so they can see the final email before sending
      const previewPage = emailEditor.getChildControl("email-content-editor-and-preview").getChildControl("preview-page");
      if (!previewPage.isVisible()) {
        const tabView = previewPage.getLayoutParent().getLayoutParent();
        tabView.setSelection([previewPage]);
        osparc.FlashMessenger.logAs(this.tr("Please preview the email before sending"), "WARNING");
        return;
      }

      if (this.getActionMode() === "approve") {
        this.__approveWithEmail();
      } else if (this.getActionMode() === "reject") {
        this.__rejectWithEmail();
      }
    },

    __approveWithEmail: function() {
      const email = this.getEmail();
      const invitationUrl = this.getInvitationUrl();
      const emailEditor = this.getChildControl("email-editor");
      const subjectField = emailEditor.getChildControl("subject-field");
      const subject = subjectField.getValue();
      const emailContentEditor = emailEditor.getChildControl("email-content-editor-and-preview");
      const bodyHtml = emailContentEditor.composeWholeHtml();
      const bodyText = emailContentEditor.getBodyText();
      const params = {
        data: {
          email,
          invitationUrl,
          messageContent: {
            subject,
            bodyHtml,
            bodyText,
          }
        }
      };
      osparc.data.Resources.fetch("poUsers", "approveUser", params)
        .then(() => {
          osparc.FlashMessenger.logAs(this.tr("User approved and email sent"), "INFO");
          this.fireEvent("userApproved");
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    __rejectWithEmail: function() {
      const email = this.getEmail();
      const invitationUrl = this.getInvitationUrl();
      const emailEditor = this.getChildControl("email-editor");
      const subjectField = emailEditor.getChildControl("subject-field");
      const subject = subjectField.getValue();
      const emailContentEditor = emailEditor.getChildControl("email-content-editor-and-preview");
      const bodyHtml = emailContentEditor.composeWholeHtml();
      const bodyText = emailContentEditor.getBodyText();
      const params = {
        data: {
          email,
          invitationUrl,
          messageContent: {
            subject,
            bodyHtml,
            bodyText,
          }
        }
      };
      osparc.data.Resources.fetch("poUsers", "rejectUser", params)
        .then(() => {
          osparc.FlashMessenger.logAs(this.tr("User rejected and email sent"), "INFO");
          this.fireEvent("userRejected");
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    __approveWithoutEmail: function() {
      const email = this.getEmail();
      const invitationUrl = this.getInvitationUrl();
      const params = {
        data: {
          email,
          invitationUrl,
          messageContent: null, // this is the trick not to send email
        }
      };
      osparc.data.Resources.fetch("poUsers", "approveUser", params)
        .then(() => {
          osparc.FlashMessenger.logAs(this.tr("User approved"), "INFO");
          this.fireEvent("userApproved");
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    __rejectWithoutEmail: function() {
      const email = this.getEmail();
      const params = {
        data: {
          email,
          messageContent: null, // this is the trick not to send email
        }
      };
      osparc.data.Resources.fetch("poUsers", "rejectUser", params)
        .then(() => {
          osparc.FlashMessenger.logAs(this.tr("User rejected"), "INFO");
          this.fireEvent("userRejected");
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },
  }
});
