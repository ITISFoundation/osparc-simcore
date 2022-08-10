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

      const phoneValidationLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5)).set({
        visibility: "excluded"
      });
      const phoneNumber = new qx.ui.form.TextField().set({
        required: true,
        placeholder: this.tr("Type your phone number")
      });
      const verifyPhoneBtn = new qx.ui.form.Button(this.tr("Verify"));
      const validationCode = new qx.ui.form.TextField().set({
        width: 50,
        enabled: false,
        required: true,
        placeholder: this.tr("Code")
      });
      const validateCodeBtn = new osparc.ui.form.FetchButton(this.tr("Validate")).set({
        enabled: false
      });
      osparc.data.Resources.getOne("config")
        .then(config => {
          if (config["login_2fa_required"]) {
            phoneValidationLayout.show();
            phoneValidationLayout.add(phoneNumber, {
              flex: 1
            });
            phoneValidationLayout.add(verifyPhoneBtn);
            phoneValidationLayout.add(validationCode);
            phoneValidationLayout.add(validateCodeBtn);

            const restartVerifyTimer = () => {
              let count = 60;
              const refreshIntervalId = setInterval(() => {
                if (count > 0) {
                  count--;
                } else {
                  clearInterval(refreshIntervalId);
                }
                verifyPhoneBtn.set({
                  label: count > 0 ? this.tr("Verify") + ` (${count})` : this.tr("Verify"),
                  enabled: count === 0
                });
              }, 1000);
            };
            verifyPhoneBtn.addListener("execute", () => {
              const isValid = osparc.auth.core.Utils.phoneNumberValidator(phoneNumber.getValue(), phoneNumber);
              if (isValid) {
                phoneNumber.setEnabled(false);
                verifyPhoneBtn.set({
                  label: this.tr("Verify") + ` (60)`
                });
                restartVerifyTimer();
                osparc.auth.Manager.getInstance().verifyPhoneNumber(email.getValue(), phoneNumber.getValue())
                  .then(data => {
                    osparc.component.message.FlashMessenger.getInstance().info(data.message);
                    validationCode.setEnabled(true);
                    validateCodeBtn.setEnabled(true);
                  })
                  .catch(err => {
                    osparc.component.message.FlashMessenger.getInstance().error(err.message);
                  });
              }
            });

            validateCodeBtn.addListener("execute", () => {
              validateCodeBtn.setFetching(true);
              osparc.auth.Manager.getInstance().validateCodeRegister(email.getValue(), validationCode.getValue())
                .then(data => {
                  osparc.component.message.FlashMessenger.getInstance().info(data.message);
                })
                .finally(() => {
                  validateCodeBtn.setFetching(false);
                });
            });
          }
        });
      this.add(phoneValidationLayout);

      const pass1 = new qx.ui.form.PasswordField().set({
        required: true,
        placeholder: this.tr("Type a password")
      });
      osparc.utils.Utils.setIdToWidget(pass1, "registrationPass1Fld");
      this.add(pass1);

      const pass2 = new qx.ui.form.PasswordField().set({
        required: true,
        placeholder: this.tr("Retype the password")
      });
      osparc.utils.Utils.setIdToWidget(pass2, "registrationPass2Fld");
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

      const resetBtn = new qx.ui.form.Button(this.tr("Reset"));
      grp.add(resetBtn, {
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
            invitation: invitation.getValue() ? invitation.getValue() : ""
          });
        }
      }, this);

      resetBtn.addListener("execute", () => {
        phoneNumber.setEnabled(true);
        validationCode.setEnabled(false);
        this.resetValues();
      }, this);

      cancelBtn.addListener("execute", e => this.fireDataEvent("done", null), this);

      this.add(grp);
    },

    __submit: function(userData) {
      osparc.auth.Manager.getInstance().register(userData)
        .then(log => {
          this.fireDataEvent("done", log.message);
          osparc.component.message.FlashMessenger.getInstance().log(log);
        })
        .catch(err => {
          const msg = err.message || this.tr("Cannot register user");
          osparc.component.message.FlashMessenger.getInstance().logAs(msg, "ERROR");
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
