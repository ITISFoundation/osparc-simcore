/** Page to reset user's password
 *
 */
qx.Class.define("qxapp.auth.ui.ResetPassPage", {
  extend: qxapp.auth.core.BaseAuthPage,

  /*
  *****************************************************************************
     MEMBERS
  *****************************************************************************
  */

  members: {

    // overrides base
    _buildPage: function() {
      let validator = new qx.ui.form.validation.Manager();

      this._addTitleHeader(this.tr("Reset Password"));

      let password = new qx.ui.form.PasswordField().set({
        required: true,
        placeholder: this.tr("Your new password")
      });
      this.add(password);

      let confirm = new qx.ui.form.PasswordField().set({
        required: true,
        placeholder: this.tr("Retype your new password")
      });
      this.add(confirm);

      validator.add(password, function(value, itemForm) {
        return qxapp.auth.core.Utils.checkPasswordSecure(value, itemForm);
      });
      validator.setValidator(function(_itemForms) {
        return qxapp.auth.core.Utils.checkSamePasswords(password, confirm);
      });

      // submit and cancel buttons
      let grp = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));

      let submitBtn = new qx.ui.form.Button(this.tr("Submit"));
      grp.add(submitBtn, {
        flex:1
      });

      let cancelBtn = new qx.ui.form.Button(this.tr("Cancel"));
      grp.add(cancelBtn, {
        flex:1
      });

      // interaction
      submitBtn.addListener("execute", function(e) {
        const valid = validator.validate();
        if (valid) {
          const code = qxapp.auth.core.Utils.findGetParameter("code");
          qxapp.auth.core.Utils.removeParameterFromUrl("page");
          qxapp.auth.core.Utils.removeParameterFromUrl("code");
          this.__submit(password.getValue(), confirm.getValue(), code);
        }
      }, this);

      cancelBtn.addListener("execute", function(e) {
        this.fireDataEvent("done", null);
      }, this);

      this.add(grp);
    },

    __submit: function(password, confirm, code) {
      let manager = qxapp.auth.Manager.getInstance();

      let successFun = function(log) {
        this.fireDataEvent("done", log.message);
        // TODO: See #465: clean all query from url: e.g. /?page=reset-password&code=qwewqefgfg
        qxapp.component.widget.FlashMessenger.getInstance().log(log);
      };

      let failFun = function(msg) {
        msg = msg || this.tr("Could not reset password");
        qxapp.component.widget.FlashMessenger.getInstance().logThis(msg, "ERROR", "user");
      };

      manager.resetPassword(password, confirm, code, successFun, failFun, this);
    }

  }
});
