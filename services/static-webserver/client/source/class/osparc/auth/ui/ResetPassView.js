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

/** Page to reset user's password
 *
 */

qx.Class.define("osparc.auth.ui.ResetPassView", {
  extend: osparc.auth.core.BaseAuthPage,

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

      let password = new osparc.ui.form.PasswordField().set({
        required: true,
        placeholder: this.tr("Your new password")
      });
      this.add(password);

      let confirm = new osparc.ui.form.PasswordField().set({
        required: true,
        placeholder: this.tr("Retype your new password")
      });
      this.add(confirm);

      const urlFragment = osparc.utils.Utils.parseURLFragment();
      const resetCode = urlFragment.params ? urlFragment.params.code || null : null;
      const code = new qx.ui.form.TextField().set({
        visibility: "excluded",
        value: resetCode
      });
      this.add(code);

      validator.add(password, osparc.auth.core.Utils.passwordLengthValidator);
      validator.add(confirm, osparc.auth.core.Utils.passwordLengthValidator);
      validator.setValidator(function(_itemForms) {
        return osparc.auth.core.Utils.checkSamePasswords(password, confirm);
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
      submitBtn.addListener("execute", e => {
        const valid = validator.validate();
        if (valid) {
          this.__submit(password.getValue(), confirm.getValue(), code.getValue());
        }
      }, this);

      cancelBtn.addListener("execute", e => {
        this.fireDataEvent("done", null);
      }, this);

      this.add(grp);
    },

    __submit: function(password, confirm, code) {
      let manager = osparc.auth.Manager.getInstance();

      let successFun = function(log) {
        this.fireDataEvent("done", log.message);
        osparc.FlashMessenger.getInstance().log(log);
      };

      let failFun = function(msg) {
        msg = msg || this.tr("Could not reset password");
        osparc.FlashMessenger.getInstance().logAs(msg, "ERROR", "user");
      };

      manager.resetPassword(password, confirm, code, successFun, failFun, this);
    }

  }
});
