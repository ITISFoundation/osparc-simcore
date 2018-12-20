/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo (pcrespov)

************************************************************************ */

/** Page to reset user's password
 *
 */
/* eslint no-warning-comments: "off" */
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
          const code = qxapp.auth.core.Utils.findParameterInFragment("code");
          qxapp.auth.core.Utils.removeParameterInFragment("page");
          qxapp.auth.core.Utils.removeParameterInFragment("code");
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
        qxapp.component.widget.FlashMessenger.getInstance().logAs(msg, "ERROR", "user");
      };

      manager.resetPassword(password, confirm, code, successFun, failFun, this);
    }

  }
});
