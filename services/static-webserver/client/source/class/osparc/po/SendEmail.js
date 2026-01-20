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

qx.Class.define("osparc.po.SendEmail", {
  extend: osparc.po.BaseView,

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "form-container": {
          control = new qx.ui.container.Composite(new qx.ui.layout.Grid(10, 5));
          control.getLayout().setColumnFlex(1, 1);
          this._add(control);
          break;
        }
        case "recipient-field": {
          control = new qx.ui.form.TextField().set({
            marginBottom: 5
          });
          const formContainer = this.getChildControl("form-container");
          formContainer.add(new qx.ui.basic.Label(this.tr("To")).set({
            paddingTop: 5,
          }), {
            row: 0,
            column: 0
          });
          formContainer.add(control, {
            row: 0,
            column: 1
          });
          break;
        }
        case "subject-field": {
          control = new qx.ui.form.TextField().set({
            marginBottom: 10
          });
          const formContainer = this.getChildControl("form-container");
          formContainer.add(new qx.ui.basic.Label(this.tr("Subject")).set({
            paddingTop: 5,
          }), {
            row: 1,
            column: 0
          });
          formContainer.add(control, {
            row: 1,
            column: 1
          });
          break;
        }
        case "email-editor": {
          control = new osparc.editor.EmailEditor();
          const container = new qx.ui.container.Scroll();
          container.add(control);
          this._add(container, {
            flex: 1
          });
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
        case "send-email-button":
          control = new qx.ui.form.Button(this.tr("Send")).set({
            appearance: "strong-button",
            allowGrowX: false
          });
          control.addListener("execute", () => this.__sendEmailClicked(), this);
          this.getChildControl("button-bar").add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    _buildLayout: function() {
      this.getChildControl("recipient-field");
      this.getChildControl("subject-field");
      this.getChildControl("email-editor");
      this.getChildControl("send-email-button");
    },

    __sendEmailClicked: function() {
      const recipientField = this.getChildControl("recipient-field");
      const subjectField = this.getChildControl("subject-field");
      const emailEditor = this.getChildControl("email-editor");
      const data = {
        to: recipientField.getValue(),
        subject: subjectField.getValue(),
        content: emailEditor.getTemplateEmail(),
      };
      osparc.store.Faker.getInstance().sendTestEmail(data)
        .then(() => {
          osparc.ui.message.FlashMessenger.getInstance().logAsSuccess(this.tr("Test email sent successfully"));
        })
        .catch(err => {
          const errorMsg = err.message || this.tr("An error occurred while sending the test email");
          osparc.ui.message.FlashMessenger.getInstance().logAsError(errorMsg);
        });
    },
  }
});
