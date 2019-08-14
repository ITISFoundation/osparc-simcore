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
 *
 *  TODO: add a check to prevent bots to register users
*/

qx.Class.define("osparc.auth.ui.RegistrationView", {
  extend: osparc.auth.core.BaseAuthPage,


  /*
  *****************************************************************************
     MEMBERS
  *****************************************************************************
  */

  members: {
    __email: null,

    // overrides base
    _buildPage: function() {
      let validator = new qx.ui.form.validation.Manager();

      this._addTitleHeader(this.tr("Registration"));

      // email, pass1 == pass2
      let email = new qx.ui.form.TextField().set({
        required: true,
        placeholder: this.tr("Introduce your email")
      });
      this.add(email);
      this.__email = email;

      // let uname = new qx.ui.form.TextField().set({
      //   required: true,
      //   placeholder: this.tr("Introduce a user name")
      // });
      // this.add(uname);

      let pass1 = new qx.ui.form.PasswordField().set({
        required: true,
        placeholder: this.tr("Introduce a password")
      });
      this.add(pass1);

      let pass2 = new qx.ui.form.PasswordField().set({
        required: true,
        placeholder: this.tr("Retype the password")
      });
      this.add(pass2);

      const urlFragment = osparc.utils.Utils.parseURLFragment();
      const token = urlFragment.params ? urlFragment.params.invitation || null : null;
      const invitation = new qx.ui.form.TextField().set({
        visibility: "excluded",
        value: token
      });
      this.add(invitation);

      // validation
      validator.add(email, qx.util.Validate.email());
      validator.setValidator(function(_itemForms) {
        return osparc.auth.core.Utils.checkSamePasswords(pass1, pass2);
      });


      // submit & cancel buttons
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
          this.__submit({
            email: email.getValue(),
            password: pass1.getValue(),
            confirm: pass2.getValue(),
            invitation: invitation.getValue() ? invitation.getValue() : ""
          });
        }
      }, this);

      cancelBtn.addListener("execute", function(e) {
        this.fireDataEvent("done", null);
      }, this);

      this.add(grp);
    },

    __submit: function(userData) {
      console.debug("Registering new user");

      let manager = osparc.auth.Manager.getInstance();

      let successFun = function(log) {
        this.fireDataEvent("done", log.message);
        osparc.component.message.FlashMessenger.getInstance().log(log);
      };

      let failFun = function(msg) {
        msg = msg || this.tr("Cannot register user");
        osparc.component.message.FlashMessenger.getInstance().logAs(msg, "ERROR");
      };

      manager.register(userData, successFun, failFun, this);
    }

  }
});
