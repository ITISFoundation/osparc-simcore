/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.auth.ui.RequestAccount", {
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
      const validator = new qx.ui.form.validation.Manager();

      this._addTitleHeader(this.tr("Registration"));

      // email, pass1 == pass2
      const email = new qx.ui.form.TextField().set({
        required: true,
        placeholder: this.tr("Type your email")
      });
      this.add(email);
      osparc.utils.Utils.setIdToWidget(email, "registrationEmailFld");
      this.addListener("appear", () => {
        email.focus();
        email.activate();
      });

      const pass1 = new osparc.ui.form.PasswordField().set({
        required: true,
        placeholder: this.tr("Type a password")
      });
      osparc.utils.Utils.setIdToWidget(pass1.getChildControl("passwordField"), "registrationPass1Fld");
      this.add(pass1);

      const pass2 = new osparc.ui.form.PasswordField().set({
        required: true,
        placeholder: this.tr("Retype the password")
      });
      osparc.utils.Utils.setIdToWidget(pass2.getChildControl("passwordField"), "registrationPass2Fld");
      this.add(pass2);

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
      submitBtn.addListener("execute", e => {
        const valid = validator.validate();
        if (valid) {
          this.__submit({
            email: email.getValue(),
            password: pass1.getValue(),
            confirm: pass2.getValue(),
            invitation: invitationToken ? invitationToken : ""
          });
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
