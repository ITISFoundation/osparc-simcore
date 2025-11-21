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
    },

    updatingNumber: {
      check: "Boolean",
      init: false,
      nullable: false,
    }
  },

  events: {
    "skipPhoneRegistration": "qx.event.type.Data"
  },

  members: {
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
            value: this.tr("If SMS is your chosen 2FA method, you'll get a text message with a code on every login to authenticate your access."),
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
          control = new osparc.ui.form.IntlTelInput();
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
          control.addListener("execute", () => this.__verifyPhoneNumber());
          this.getChildControl("phone-number-layout").add(control);
          break;
        case "validation-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5)).set({
            zIndex: 1 // the countries list that goes on top has a z-index of 2
          });
          this.add(control);
          break;
        case "validate-code-field":
          control = new qx.ui.form.TextField().set({
            placeholder: this.tr("Type the SMS code"),
            enabled: false,
            height: 29, // to align it with the strong button next to it
          });
          control.addListener("input", e => this.getChildControl("validate-code-button").setEnabled(Boolean(e.getData())));
          this.getChildControl("validation-layout").add(control, {
            flex: 1
          });
          break;
        case "validate-code-button":
          control = new osparc.ui.form.FetchButton(this.tr("Validate")).set({
            appearance: "strong-button",
            center: true,
            enabled: false,
            minWidth: 80,
          });
          control.addListener("execute", () => this.__validateCodeRegister());
          this.getChildControl("validation-layout").add(control);
          break;
        case "send-via-email-button":
          control = new osparc.ui.form.FetchButton().set({
            label: this.tr("Skip phone registration and send code via email"),
            textColor: "text",
            zIndex: 1 // the countries list that goes on top has a z-index of 2
          });
          control.addListener("execute", () => this.__requestCodeViaEmail(), this);
          this.add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    _buildPage: function() {
      this.getChildControl("title");
      this.getChildControl("intro-text");

      this.getChildControl("intl-tel-input");
      this.getChildControl("verify-number-button");

      this.getChildControl("validate-code-field");
      this.getChildControl("validate-code-button");

      this.getChildControl("send-via-email-button");
    },

    __verifyPhoneNumber: function() {
      const itiInput = this.getChildControl("intl-tel-input");
      const verifyPhoneNumberBtn = this.getChildControl("verify-number-button");
      const validateCodeBtn = this.getChildControl("validate-code-button");
      itiInput.verifyPhoneNumber();
      const isValid = itiInput.isValidNumber();
      if (isValid) {
        itiInput.setEnabled(false);
        verifyPhoneNumberBtn.setFetching(true);
        const promise = this.isUpdatingNumber() ?
          osparc.auth.Manager.getInstance().updatePhoneNumber(itiInput.getNumber()) :
          osparc.auth.Manager.getInstance().verifyPhoneNumber(this.getUserEmail(), itiInput.getNumber());
        promise
          .then(resp => {
            const msg = (resp && resp.message) ? resp.message : "A verification code has been sent via SMS";
            osparc.FlashMessenger.logAs(msg, "INFO");
            verifyPhoneNumberBtn.setFetching(false);
            verifyPhoneNumberBtn.setEnabled(false);
            const resendCodeTimeout = 10000;
            setTimeout(() => verifyPhoneNumberBtn.setEnabled(true), resendCodeTimeout);
            // enable, focus and listen to Enter
            const validateCodeField = this.getChildControl("validate-code-field");
            validateCodeField.setEnabled(true);
            validateCodeField.focus();
            validateCodeField.activate();
            this.__enableEnterCommand(validateCodeBtn);
          })
          .catch(err => {
            osparc.FlashMessenger.logError(err);
            verifyPhoneNumberBtn.setFetching(false);
            itiInput.setEnabled(true);
          });
      }
    },

    __validateCodeRegister: function() {
      const validateCodeField = this.getChildControl("validate-code-field");
      const validateCodeBtn = this.getChildControl("validate-code-button");

      validateCodeBtn.setFetching(true);

      const loginFun = log => {
        const msg = (log && log.message) ? log.message : "The phone number was updated successfully";
        osparc.FlashMessenger.logAs(msg, "INFO");
        validateCodeField.setEnabled(false);
        validateCodeBtn.setFetching(false);
        validateCodeBtn.setEnabled(false);
        validateCodeBtn.setIcon("@FontAwesome5Solid/check/12");
        this.fireDataEvent("done", msg);
      };

      const failFun = err => {
        osparc.FlashMessenger.logError(err);
        validateCodeBtn.setFetching(false);
        // TODO: can get field info from response here
        err = String(err) || this.tr("Invalid code");
        validateCodeField.set({
          invalidMessage: err,
          valid: false
        });
      };

      const manager = osparc.auth.Manager.getInstance();
      const itiInput = this.getChildControl("intl-tel-input");
      if (this.isUpdatingNumber()) {
        manager.validateCodeUpdatePhoneNumber(validateCodeField.getValue(), loginFun, failFun, this);
      } else {
        manager.validateCodeRegister(this.getUserEmail(), itiInput.getNumber(), validateCodeField.getValue(), loginFun, failFun, this);
      }
    },

    __requestCodeViaEmail: function() {
      const sendViaEmail = this.getChildControl("send-via-email-button");
      sendViaEmail.setFetching(true);
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
        .finally(() => sendViaEmail.setFetching(false));
    },

    __enableEnterCommand: function(onBtn) {
      this.__disableCommands();

      const commandEnter = new qx.ui.command.Command("Enter");
      onBtn.setCommand(commandEnter);
    },

    __disableCommands: function() {
      const verifyPhoneNumberBtn = this.getChildControl("verify-number-button");
      verifyPhoneNumberBtn.setCommand(null);

      const validateCodeBtn = this.getChildControl("validate-code-button");
      validateCodeBtn.setCommand(null);
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
