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
    __submitBtn: null,

    // overrides base
    _buildPage: function() {
      this._addTitleHeader(this.tr("Reset Password"));

      // form
      const password = new osparc.ui.form.PasswordField().set({
        required: true
      });
      this._form.add(password, this.tr("Your new password"), null, "password1");
      this.add(password);

      const confirm = new osparc.ui.form.PasswordField().set({
        required: true
      });
      this._form.add(confirm, this.tr("Retype your new password"), null, "password2");

      const urlFragment = osparc.utils.Utils.parseURLFragment();
      const resetCode = urlFragment.params ? urlFragment.params.code || null : null;
      const code = new qx.ui.form.TextField().set({
        visibility: "excluded",
        value: resetCode
      });
      this.add(code);

      const validator = new qx.ui.form.validation.Manager();
      validator.add(password, osparc.auth.core.Utils.passwordLengthValidator);
      validator.add(confirm, osparc.auth.core.Utils.passwordLengthValidator);
      validator.setValidator(function(_itemForms) {
        return osparc.auth.core.Utils.checkSamePasswords(password, confirm);
      });

      this.beautifyFormFields();
      const formRenderer = new qx.ui.form.renderer.SinglePlaceholder(this._form);
      this.add(formRenderer);

      // buttons
      const grp = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));

      const submitBtn = this.__submitBtn = new osparc.ui.form.FetchButton(this.tr("Submit")).set({
        center: true,
        appearance: "strong-button",
      });
      grp.addAt(submitBtn, 1, {
        flex:1
      });

      const cancelBtn = new qx.ui.form.Button(this.tr("Cancel")).set({
        appearance: "form-button-text"
      });
      grp.addAt(cancelBtn, 0, {
        flex:1
      });

      // interaction
      submitBtn.addListener("execute", () => {
        if (this._form.validate()) {
          const valid = validator.validate();
          if (valid) {
            this.__submit(password.getValue(), confirm.getValue(), code.getValue());
          }
        }
      }, this);

      cancelBtn.addListener("execute", () => this.fireDataEvent("done", null), this);

      this.add(grp);
    },

    __submit: function(password, confirm, code) {
      this.__submitBtn.setFetching(true);

      const successFun = log => {
        this.__submitBtn.setFetching(false);
        this.fireDataEvent("done", log.message);
        osparc.FlashMessenger.getInstance().log(log);
      };

      const failFun = err => {
        this.__submitBtn.setFetching(false);
        osparc.FlashMessenger.logError(err, this.tr("Could not reset password"));
      };

      const manager = osparc.auth.Manager.getInstance();
      manager.resetPassword(password, confirm, code, successFun, failFun, this);
    }

  }
});
