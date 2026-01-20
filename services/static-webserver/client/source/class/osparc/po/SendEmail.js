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
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
            alignX: "right",
            padding: 10
          }));
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
      this.getChildControl("email-editor");
      this.getChildControl("send-email-button");
    },

    __sendEmailClicked: function() {
      const emailEditor = this.getChildControl("email-editor");
      const emailContent = emailEditor.getTemplateEmail();
      osparc.store.Faker.getInstance().sendTestEmail(emailContent)
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
