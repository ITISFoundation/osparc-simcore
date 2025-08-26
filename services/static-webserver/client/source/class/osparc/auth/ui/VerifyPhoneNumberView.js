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
    __validateCodeField: null,
    __validateCodeBtn: null,
    __sendViaEmail: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "title":
          control = new qx.ui.basic.Label().set({
            value: this.tr("Two-Factor Authentication (2FA)"),
            allowGrowX: true,
            rich: true,
            font: "text-16"
          });
          this.add(control);
          break;
        case "intro-text":
          control = new qx.ui.basic.Label().set({
            value: this.tr("A text message will be sent to your mobile phone for authentication each time you log in."),
            rich: true,
            wrap: true
          });
          this.add(control);
          break;
        case "phone-number-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
          control.getContentElement().setStyles({
            "overflow": "visible" // needed for countries dropdown menu
          });
          this.add(control);
          break;
        case "intl-tel-input":
          control = new osparc.widget.IntlTelInput();
          this.getChildControl("phone-number-layout").add(control, {
            flex: 1
          });
          break;
        case "verify-number-button":
          control = new osparc.ui.form.FetchButton(this.tr("Send SMS")).set({
            appearance: "strong-button",
            center: true,
            minWidth: 80
          });
          this.getChildControl("phone-number-layout").add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

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
      this.getChildControl("title");
      this.getChildControl("intro-text");

      this.getChildControl("intl-tel-input");
      this.getChildControl("verify-number-button");
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
      const verifyPhoneNumberBtn = this.getChildControl("verify-number-button");
      verifyPhoneNumberBtn.addListener("execute", () => this.__verifyPhoneNumber());
      this.__validateCodeBtn.addListener("execute", () => this.__validateCodeRegister());
      this.__sendViaEmail.addListener("execute", () => this.__requestCodeViaEmail(), this);
    },

    __verifyPhoneNumber: function() {
      const itiInput = this.getChildControl("intl-tel-input");
      const verifyPhoneNumberBtn = this.getChildControl("verify-number-button");
      itiInput.verifyPhoneNumber();
      const isValid = itiInput.isValidNumber();
      if (isValid) {
        itiInput.setEnabled(false);
        verifyPhoneNumberBtn.setFetching(true);
        osparc.auth.Manager.getInstance().verifyPhoneNumber(this.getUserEmail(), itiInput.getNumber())
          .then(resp => {
            osparc.FlashMessenger.logAs(resp.message, "INFO");
            verifyPhoneNumberBtn.setFetching(false);
            // enable, focus and listen to Enter
            this.__validateCodeField.setEnabled(true);
            this.__validateCodeField.focus();
            this.__validateCodeField.activate();
            this.__enableEnterCommand(this.__validateCodeBtn);
          })
          .catch(err => {
            osparc.FlashMessenger.logError(err);
            verifyPhoneNumberBtn.setFetching(false);
            itiInput.setEnabled(true);
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

      const failFun = err => {
        osparc.FlashMessenger.logError(err);
        this.__validateCodeBtn.setFetching(false);
        // TODO: can get field info from response here
        err = String(err) || this.tr("Invalid code");
        this.__validateCodeField.set({
          invalidMessage: err,
          valid: false
        });
      };

      const manager = osparc.auth.Manager.getInstance();
      const itiInput = this.getChildControl("intl-tel-input");
      manager.validateCodeRegister(this.getUserEmail(), itiInput.getNumber(), this.__validateCodeField.getValue(), loginFun, failFun, this);
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
        .catch(err => osparc.FlashMessenger.logError(err))
        .finally(() => this.__sendViaEmail.setFetching(false));
    },

    __enableEnterCommand: function(onBtn) {
      this.__disableCommands();

      const commandEnter = new qx.ui.command.Command("Enter");
      onBtn.setCommand(commandEnter);
    },

    __disableCommands: function() {
      const verifyPhoneNumberBtn = this.getChildControl("verify-number-button");
      verifyPhoneNumberBtn.setCommand(null);
      this.__validateCodeBtn.setCommand(null);
    },

    _onAppear: function() {
      const verifyPhoneNumberBtn = this.getChildControl("verify-number-button");
      this.__enableEnterCommand(verifyPhoneNumberBtn);
    },

    _onDisappear: function() {
      this.__disableCommands();
    }
  }
});
