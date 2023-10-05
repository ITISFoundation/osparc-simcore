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
    __submitBtn: null,
    __cancelBtn: null,

    // overrides base
    _buildPage: function() {
      this._addTitleHeader(this.tr("Registration"));

      const formRenderer = new qx.ui.form.renderer.SinglePlaceholder(this._form);
      this.add(formRenderer);

      // email, pass1 == pass2
      const email = new qx.ui.form.TextField().set({
        required: true
      });
      osparc.utils.Utils.setIdToWidget(email, "registrationEmailFld");
      this._form.add(email, this.tr("Type your email"), null, "email");
      this.addListener("appear", () => {
        email.focus();
        email.activate();
      });

      const pass1 = new osparc.ui.form.PasswordField().set({
        required: true
      });
      osparc.utils.Utils.setIdToWidget(pass1.getChildControl("passwordField"), "registrationPass1Fld");
      this._form.add(email, this.tr("Type a password"), null, "pass1");

      const pass2 = new osparc.ui.form.PasswordField().set({
        required: true
      });
      osparc.utils.Utils.setIdToWidget(pass2.getChildControl("passwordField"), "registrationPass2Fld");
      this._form.add(pass2, this.tr("Retype the password"), null, "pass2");

      const urlFragment = osparc.utils.Utils.parseURLFragment();
      const invitationToken = urlFragment.params ? urlFragment.params.invitation || null : null;
      if (invitationToken) {
        osparc.auth.Manager.getInstance().checkInvitation(invitationToken)
          .then(data => {
            if (data && data.email) {
              email.set({
                value: data.email,
                enabled: false
              });
            }
          });
      }

      // validation
      const validator = new qx.ui.form.validation.Manager();
      validator.add(email, qx.util.Validate.email());
      validator.add(pass1, osparc.auth.core.Utils.passwordLengthValidator);
      validator.add(pass2, osparc.auth.core.Utils.passwordLengthValidator);
      validator.setValidator(() => osparc.auth.core.Utils.checkSamePasswords(pass1, pass2));

      // submit & cancel buttons
      const grp = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));

      const submitBtn = this.__submitBtn = new qx.ui.form.Button(this.tr("Submit")).set({
        center: true,
        appearance: "strong-button"
      });
      osparc.utils.Utils.setIdToWidget(submitBtn, "registrationSubmitBtn");
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
          const valid = validator.validate();
          if (valid) {
            this.__submit({
              email: email.getValue(),
              password: pass1.getValue(),
              confirm: pass2.getValue(),
              invitation: invitationToken ? invitationToken : ""
            });
          }
        }
      }, this);

      cancelBtn.addListener("execute", e => this.fireDataEvent("done", null), this);

      this.add(grp);
    },

    __submit: function(userData) {
      osparc.auth.Manager.getInstance().register(userData)
        .then(log => {
          this.fireDataEvent("done", log.message);
          osparc.FlashMessenger.getInstance().log(log);
        })
        .catch(err => {
          const msg = err.message || this.tr("Cannot register user");
          osparc.FlashMessenger.getInstance().logAs(msg, "ERROR");
        });
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
