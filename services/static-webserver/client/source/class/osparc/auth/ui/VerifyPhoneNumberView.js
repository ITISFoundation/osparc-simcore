/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaz)

************************************************************************ */


qx.Class.define("osparc.auth.ui.VerifyPhoneNumberView", {
  extend: osparc.auth.core.BaseAuthPage,

  properties: {
    userEmail: {
      check: "String",
      init: "foo@mymail.com",
      nullable: false
    }
  },

  statics: {
    restartResendTimer: function(button, buttonText) {
      let count = 60;
      const refreshIntervalId = setInterval(() => {
        if (count > 0) {
          count--;
        } else {
          clearInterval(refreshIntervalId);
        }
        button.set({
          label: count > 0 ? buttonText + ` (${count})` : buttonText,
          enabled: count === 0
        });
      }, 1000);
    }
  },

  members: {
    __phoneNumberTF: null,
    __verifyPhoneNumberBtn: null,
    __validateCodeTF: null,
    __validateCodeBtn: null,
    __resendCodeBtn: null,

    _buildPage: function() {
      this.__buildVerificationLayout();
      this.__buildValidationLayout();
      this.__attachHandlers();
    },

    __buildVerificationLayout: function() {
      const verificationInfoTitle = new qx.ui.basic.Label().set({
        value: this.tr("Two-Factor Authentication (2FA)"),
        font: "text-16"
      });
      this.add(verificationInfoTitle);
      const verificationInfoDesc = new qx.ui.basic.Label().set({
        value: this.tr("We will send you a text message to your mobile phone to authenticate you each time you log in."),
        rich: true,
        wrap: true
      });
      this.add(verificationInfoDesc);

      const phoneNumberVerifyLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      const phoneNumber = this.__phoneNumberTF = new qx.ui.form.TextField().set({
        required: true,
        placeholder: this.tr("Type your phone number")
      });
      phoneNumberVerifyLayout.add(phoneNumber, {
        flex: 1
      });
      const msg = this.tr("Phone number in <a href='https://en.wikipedia.org/wiki/E.164' target='_blank'>E.164 format</a>");
      const infoButton = new osparc.ui.hint.InfoHint(msg).set({
        alignY: "middle"
      });
      phoneNumberVerifyLayout.add(infoButton);
      const verifyPhoneNumberBtn = this.__verifyPhoneNumberBtn = new qx.ui.form.Button(this.tr("Send SMS")).set({
        minWidth: 80
      });
      phoneNumberVerifyLayout.add(verifyPhoneNumberBtn);
      this.add(phoneNumberVerifyLayout);
    },

    __buildValidationLayout: function() {
      const smsValidationLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      const validationCode = this.__validateCodeTF = new qx.ui.form.TextField().set({
        placeholder: this.tr("Type the SMS code"),
        enabled: false
      });
      smsValidationLayout.add(validationCode, {
        flex: 1
      });
      const validateCodeBtn = this.__validateCodeBtn = new osparc.ui.form.FetchButton(this.tr("Validate")).set({
        minWidth: 80,
        enabled: false
      });
      smsValidationLayout.add(validateCodeBtn);
      this.add(smsValidationLayout);
    },

    __attachHandlers: function() {
      this.__verifyPhoneNumberBtn.addListener("execute", () => this.__verifyPhoneNumber());
      this.__validateCodeBtn.addListener("execute", () => this.__validateCodeRegister());
    },

    __verifyPhoneNumber: function() {
      const isValid = osparc.auth.core.Utils.phoneNumberValidator(this.__phoneNumberTF.getValue(), this.__phoneNumberTF);
      if (isValid) {
        this.__phoneNumberTF.setEnabled(false);
        this.__verifyPhoneNumberBtn.setEnabled(false);
        this.self().restartResendTimer(this.__verifyPhoneNumberBtn, this.tr("Send SMS"));
        osparc.auth.Manager.getInstance().verifyPhoneNumber(this.getUserEmail(), this.__phoneNumberTF.getValue())
          .then(data => {
            osparc.component.message.FlashMessenger.logAs(data.message, "INFO");
            this.__validateCodeTF.setEnabled(true);
            this.__validateCodeBtn.setEnabled(true);
          })
          .catch(err => {
            osparc.component.message.FlashMessenger.logAs(err.message, "ERROR");
            this.__phoneNumberTF.setEnabled(true);
          });
      }
    },

    __validateCodeRegister: function() {
      this.__validateCodeBtn.setFetching(true);

      const loginFun = log => {
        osparc.component.message.FlashMessenger.logAs(log.message, "INFO");
        this.__validateCodeBtn.setFetching(false);
        this.__validateCodeTF.setEnabled(false);
        this.__validateCodeBtn.setEnabled(false);
        this.__validateCodeBtn.setIcon("@FontAwesome5Solid/check/12");
        this.fireDataEvent("done", log.message);
      };

      const failFun = msg => {
        osparc.component.message.FlashMessenger.getInstance().logAs(msg, "ERROR");
        this.__validateCodeBtn.setFetching(false);
        // TODO: can get field info from response here
        msg = String(msg) || this.tr("Invalid code");
        this.__validateCodeTF.set({
          invalidMessage: msg,
          valid: false
        });
      };

      const manager = osparc.auth.Manager.getInstance();
      manager.validateCodeRegister(this.getUserEmail(), this.__phoneNumberTF.getValue(), this.__validateCodeTF.getValue(), loginFun, failFun, this);
    }
  }
});
