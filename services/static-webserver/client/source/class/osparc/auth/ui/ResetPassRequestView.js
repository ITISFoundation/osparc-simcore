/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo (pcrespov)

************************************************************************ */

/** Page to request password reset for a non-logged-in user
 *
 */

qx.Class.define("osparc.auth.ui.ResetPassRequestView", {
  extend: osparc.auth.core.BaseAuthPage,

  /*
  *****************************************************************************
     MEMBERS
  *****************************************************************************
  */

  members: {
    __submitBtn: null,
    __cancelBtn: null,

    // overrides base
    _buildPage: function() {
      this._addTitleHeader(this.tr("Reset Password"));

      // form
      // email
      const email = new qx.ui.form.TextField().set({
        required: true
      });
      email.setRequired(true);
      this._form.add(email, this.tr("Type your registration email"), qx.util.Validate.email(), "email");
      this.addListener("appear", () => {
        email.focus();
        email.activate();
      });

      Object.values(this._form.getItems()).forEach(formItem => formItem.setWidth(osparc.auth.core.BaseAuthPage.FORM_WIDTH));
      const formRenderer = new qx.ui.form.renderer.SinglePlaceholder(this._form);
      this.add(formRenderer);

      // buttons
      const grp = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));

      const submitBtn = this.__submitBtn = new qx.ui.form.Button(this.tr("Submit")).set({
        center: true,
        appearance: "strong-button"
      });
      grp.add(submitBtn, {
        flex:1
      });

      const cancelBtn = this.__cancelBtn = new qx.ui.form.Button(this.tr("Cancel"));
      grp.add(cancelBtn, {
        flex:1
      });

      // interaction
      submitBtn.addListener("execute", () => {
        if (this._form.validate()) {
          this.__submit(email);
        }
      }, this);

      cancelBtn.addListener("execute", () => this.fireDataEvent("done", null), this);

      this.add(grp);
    },

    __submit: function(email) {
      const manager = osparc.auth.Manager.getInstance();

      const successFun = log => {
        this.fireDataEvent("done", log.message);
        osparc.FlashMessenger.getInstance().log(log);
      };

      const failFun = msg => {
        msg = msg || this.tr("Could not request password reset");
        osparc.FlashMessenger.getInstance().logAs(msg, "ERROR");
      };

      manager.resetPasswordRequest(email.getValue(), successFun, failFun, this);
    },

    _onAppear: function() {
      // Listen to "Enter" key
      const commandEnter = new qx.ui.command.Command("Enter");
      this.__submitBtn.setCommand(commandEnter);

      // Listen to "Esc" key
      const commandEsc = new qx.ui.command.Command("Esc");
      this.__cancelBtn.setCommand(commandEsc);
    },

    _onDisappear: function() {
      this.__submitBtn.setCommand(null);
      this.__cancelBtn.setCommand(null);
    }
  }
});
