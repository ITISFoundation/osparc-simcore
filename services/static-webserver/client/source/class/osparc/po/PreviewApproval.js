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

qx.Class.define("osparc.po.PreviewApproval", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__buildLayout();
  },

  properties: {
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
          control = new osparc.ui.form.FetchButton(this.tr("Approve without sending email")).set({
            allowGrowX: false
          });
          control.addListener("execute", () => this.fireDataEvent("approveWithoutEmail"), this);
          this.getChildControl("button-bar").add(control);
          break;
        case "send-email-button":
          control = new osparc.ui.form.FetchButton(this.tr("Send")).set({
            appearance: "strong-button",
            allowGrowX: false
          });
          control.addListener("execute", () => this.__sendEmailClicked(), this);
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
      this.getChildControl("send-email-button");
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
  }
});
