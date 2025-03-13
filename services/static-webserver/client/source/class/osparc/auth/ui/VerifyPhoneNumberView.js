/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

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

  events: {
    "skipPhoneRegistration": "qx.event.type.Data"
  },

  members: {
    __itiInput: null,
    __verifyPhoneNumberBtn: null,
    __validateCodeField: null,
    __validateCodeBtn: null,
    __sendViaEmail: null,

    _buildPage: function() {
      this.__buildVerificationLayout();
      const validationLayout = this.__createValidationLayout().set({
        zIndex: 1 // the countries list that goes on top has a z-index of 2
      });
      this.add(validationLayout);
      const sendViaEmailBtn = this.__createSendViaEmailButton().set({
        zIndex: 1 // the countries list that goes on top has a z-index of 2
      });
      this.add(sendViaEmailBtn);
      this.__attachHandlers();
    },

    __buildVerificationLayout: function() {
      const verificationInfoTitle = new qx.ui.basic.Label().set({
        value: this.tr("Two-Factor Authentication (2FA)"),
        allowGrowX: true,
        rich: true,
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
      phoneNumberVerifyLayout.getContentElement().setStyles({
        "overflow": "visible" // needed for countries dropdown menu
      });

      const itiInput = this.__itiInput = new osparc.widget.IntlTelInput();
      phoneNumberVerifyLayout.add(itiInput, {
        flex: 1
      });

      const verifyPhoneNumberBtn = this.__verifyPhoneNumberBtn = new osparc.ui.form.FetchButton(this.tr("Send SMS")).set({
        appearance: "strong-button",
        center: true,
        minWidth: 80
      });
      phoneNumberVerifyLayout.add(verifyPhoneNumberBtn);
      this.add(phoneNumberVerifyLayout);
    },

    __createValidationLayout: function() {
      const smsValidationLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      const validateCodeTF = this.__validateCodeField = new qx.ui.form.TextField().set({
        placeholder: this.tr("Type the SMS code"),
        enabled: false
      });
      smsValidationLayout.add(validateCodeTF, {
        flex: 1
      });
      const validateCodeBtn = this.__validateCodeBtn = new osparc.ui.form.FetchButton(this.tr("Validate")).set({
        appearance: "strong-button",
        center: true,
        minWidth: 80
      });
      validateCodeBtn.setEnabled(false);
      validateCodeTF.addListener("input", e => validateCodeBtn.setEnabled(Boolean(e.getData())));
      smsValidationLayout.add(validateCodeBtn);
      return smsValidationLayout;
    },

    __createSendViaEmailButton: function() {
      const txt = this.tr("Skip phone registration and send code via email");
      const sendViaEmail = this.__sendViaEmail = new osparc.ui.form.FetchButton(txt).set({
        textColor: "text",
        zIndex: 1 // the countries list that goes on top has a z-index of 2
      });
      return sendViaEmail;
    },

    __attachHandlers: function() {
      this.__verifyPhoneNumberBtn.addListener("execute", () => this.__verifyPhoneNumber());
      this.__validateCodeBtn.addListener("execute", () => this.__validateCodeRegister());
      this.__sendViaEmail.addListener("execute", () => this.__requestCodeViaEmail(), this);
    },

    __verifyPhoneNumber: function() {
      this.__itiInput.verifyPhoneNumber();
      const isValid = this.__itiInput.isValidNumber();
      if (isValid) {
        this.__itiInput.setEnabled(false);
        this.__verifyPhoneNumberBtn.setFetching(true);
        osparc.auth.Manager.getInstance().verifyPhoneNumber(this.getUserEmail(), this.__itiInput.getNumber())
          .then(resp => {
            osparc.FlashMessenger.logAs(resp.message, "INFO");
            this.__verifyPhoneNumberBtn.setFetching(false);
            // enable, focus and listen to Enter
            this.__validateCodeField.setEnabled(true);
            this.__validateCodeField.focus();
            this.__validateCodeField.activate();
            this.__enableEnterCommand(this.__validateCodeBtn);
          })
          .catch(err => {
            osparc.FlashMessenger.logAs(err, "ERROR");
            this.__verifyPhoneNumberBtn.setFetching(false);
            this.__itiInput.setEnabled(true);
          });
      }
    },

    __validateCodeRegister: function() {
      this.__validateCodeBtn.setFetching(true);

      const loginFun = log => {
        osparc.FlashMessenger.logAs(log.message, "INFO");
        this.__validateCodeBtn.setFetching(false);
        this.__validateCodeField.setEnabled(false);
        this.__validateCodeBtn.setEnabled(false);
        this.__validateCodeBtn.setIcon("@FontAwesome5Solid/check/12");
        this.fireDataEvent("done", log.message);
      };

      const failFun = msg => {
        osparc.FlashMessenger.logAs(msg, "ERROR");
        this.__validateCodeBtn.setFetching(false);
        // TODO: can get field info from response here
        msg = String(msg) || this.tr("Invalid code");
        this.__validateCodeField.set({
          invalidMessage: msg,
          valid: false
        });
      };

      const manager = osparc.auth.Manager.getInstance();
      manager.validateCodeRegister(this.getUserEmail(), this.__itiInput.getNumber(), this.__validateCodeField.getValue(), loginFun, failFun, this);
    },

    __requestCodeViaEmail: function() {
      this.__sendViaEmail.setFetching(true);
      osparc.auth.Manager.getInstance().resendCodeViaEmail(this.getUserEmail())
        .then(data => {
          const message = osparc.auth.core.Utils.extractMessage(data);
          const retryAfter = osparc.auth.core.Utils.extractRetryAfter(data)
          osparc.FlashMessenger.logAs(message, "INFO");
          this.fireDataEvent("skipPhoneRegistration", {
            userEmail: this.getUserEmail(),
            message,
            retryAfter
          });
        })
        .catch(err => osparc.FlashMessenger.logAs(err, "ERROR"))
        .finally(() => this.__sendViaEmail.setFetching(false));
    },

    __enableEnterCommand: function(onBtn) {
      this.__disableCommands();

      const commandEnter = new qx.ui.command.Command("Enter");
      onBtn.setCommand(commandEnter);
    },

    __disableCommands: function() {
      this.__verifyPhoneNumberBtn.setCommand(null);
      this.__validateCodeBtn.setCommand(null);
    },

    _onAppear: function() {
      this.__enableEnterCommand(this.__verifyPhoneNumberBtn);
    },

    _onDisappear: function() {
      this.__disableCommands();
    }
  }
});
