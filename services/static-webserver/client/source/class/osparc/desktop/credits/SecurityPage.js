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

/**
 *  Security page
 *
 *  - reset password (logged in)
 *
 */

qx.Class.define("osparc.desktop.credits.SecurityPage", {
  extend: osparc.desktop.preferences.pages.BasePage,

  construct: function() {
    const iconSrc = "@FontAwesome5Solid/shield-alt/24";
    const title = this.tr("Security Settings");
    this.base(arguments, title, iconSrc);

    this.add(this.__createPasswordSection());
  },

  members: {
    __createPasswordSection: function() {
      // layout
      const box = this._createSectionBox(this.tr("Password"));
      box.set({
        alignX: "left",
        maxWidth: 500
      });

      const currentPassword = new osparc.ui.form.PasswordField().set({
        tabIndex: 1,
        required: true,
        placeholder: this.tr("Your current password")
      });

      const newPassword = new osparc.ui.form.PasswordField().set({
        tabIndex: 2,
        required: true,
        placeholder: this.tr("Your new password")
      });

      const confirm = new osparc.ui.form.PasswordField().set({
        tabIndex: 3,
        required: true,
        placeholder: this.tr("Retype your new password")
      });

      const form = new qx.ui.form.Form();
      form.add(currentPassword, "Current Password", null, "curPassword");
      form.add(newPassword, "New Password", null, "newPassword");
      form.add(confirm, "Confirm New Password", null, "newPassword2");
      box.add(new qx.ui.form.renderer.Single(form));

      const manager = new qx.ui.form.validation.Manager();
      manager.add(newPassword, osparc.auth.core.Utils.passwordLengthValidator);
      manager.add(confirm, osparc.auth.core.Utils.passwordLengthValidator);
      manager.setValidator(function(_itemForms) {
        return osparc.auth.core.Utils.checkSamePasswords(newPassword, confirm);
      });

      const resetBtn = new qx.ui.form.Button("Reset Password").set({
        allowGrowX: false
      });
      box.add(resetBtn);

      resetBtn.addListener("execute", () => {
        if (manager.validate()) {
          const params = {
            data: {
              current: currentPassword.getValue(),
              new: newPassword.getValue(),
              confirm: confirm.getValue()
            }
          };
          osparc.data.Resources.fetch("password", "post", params)
            .then(data => {
              osparc.component.message.FlashMessenger.getInstance().log(data);
              [currentPassword, newPassword, confirm].forEach(item => {
                item.resetValue();
              });
            })
            .catch(err => {
              console.error(err);
              osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Failed to reset password"), "ERROR");
              [currentPassword, newPassword, confirm].forEach(item => {
                item.resetValue();
              });
            });
        }
      });

      return box;
    }
  }
});
