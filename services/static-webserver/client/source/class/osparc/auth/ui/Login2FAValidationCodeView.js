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


qx.Class.define("osparc.auth.ui.Login2FAValidationCodeView", {
  extend: osparc.auth.core.BaseAuthPage,

  properties: {
    userEmail: {
      check: "String",
      init: "foo@mymail.com",
      nullable: false
    },

    smsEnabled: {
      check: "Boolean",
      init: false,
      nullable: true,
      event: "changeSmsEnabled"
    },

    message: {
      check: "String",
      init: "We just sent a 6-digit code",
      nullable: false,
      event: "changeMessage"
    }
  },

  statics: {
    restartResendTimer: function(button, buttonText, count = 60) {
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
    __validateCodeBtn: null,
    __resendCodeSMSBtn: null,
    __resendCodeEmailBtn: null,

    _buildPage: function() {
      const introText = new qx.ui.basic.Label().set({
        rich: true
      });
      this.bind("message", introText, "value");
      this.add(introText);

      // form
      const validateCodeTF = new qx.ui.form.TextField().set({
        required: true
      });
      this._form.add(validateCodeTF, this.tr("Type code"), null, "validationCode");
      this.addListener("appear", () => {
        validateCodeTF.focus();
        validateCodeTF.activate();
      });

      this.beautifyFormFields();
      const formRenderer = new qx.ui.form.renderer.SinglePlaceholder(this._form);
      this.add(formRenderer);

      // buttons
      const validateCodeBtn = this.__validateCodeBtn = new osparc.ui.form.FetchButton(this.tr("Validate")).set({
        center: true,
        appearance: "strong-button"
      });
      validateCodeBtn.setEnabled(false);
      validateCodeTF.addListener("input", e => validateCodeBtn.setEnabled(Boolean(e.getData())));
      validateCodeBtn.addListener("execute", () => this.__validateCodeLogin(), this);
      this.add(validateCodeBtn);

      const resendLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5).set({
        alignY: "middle"
      }));
      const resendCodeDesc = new qx.ui.basic.Label().set({
        value: this.tr("Didn't receive the code? Resend code")
      });
      resendLayout.add(resendCodeDesc);

      const resendButtonsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignY: "middle"
      }));
      resendLayout.add(resendButtonsLayout);

      const resendCodeSMSBtn = this.__resendCodeSMSBtn = new osparc.ui.form.FetchButton(this.tr("Via SMS"));
      this.bind("smsEnabled", resendCodeSMSBtn, "visibility", {
        converter: smsEnabled => smsEnabled ? "visible" : "excluded"
      });
      resendButtonsLayout.add(resendCodeSMSBtn, {
        flex: 1
      });
      resendCodeSMSBtn.addListener("execute", () => {
        resendCodeSMSBtn.setFetching(true);
        osparc.auth.Manager.getInstance().resendCodeViaSMS(this.getUserEmail())
          .then(resp => {
            const message = osparc.auth.core.Utils.extractMessage(resp);
            const retryAfter = osparc.auth.core.Utils.extractRetryAfter(resp);
            osparc.FlashMessenger.logAs(message, "INFO");
            this.set({
              message
            });
            this.restartSMSButton(retryAfter);
          })
          .catch(err => osparc.FlashMessenger.logAs(err, "ERROR"))
          .finally(() => resendCodeSMSBtn.setFetching(false));
      }, this);

      const resendCodeEmailBtn = this.__resendCodeEmailBtn = new osparc.ui.form.FetchButton(this.tr("Via email"));
      resendButtonsLayout.add(resendCodeEmailBtn, {
        flex: 1
      });
      resendCodeEmailBtn.addListener("execute", () => {
        resendCodeEmailBtn.setFetching(true);
        osparc.auth.Manager.getInstance().resendCodeViaEmail(this.getUserEmail())
          .then(resp => {
            const message = osparc.auth.core.Utils.extractMessage(resp);
            const retryAfter = osparc.auth.core.Utils.extractRetryAfter(resp);
            osparc.FlashMessenger.logAs(message, "INFO");
            this.set({
              message
            });
            this.restartEmailButton(retryAfter);
          })
          .catch(err => osparc.FlashMessenger.logAs(err, "ERROR"))
          .finally(() => resendCodeEmailBtn.setFetching(false));
      }, this);
      this.add(resendLayout);
    },

    restartSMSButton: function(retryAfter) {
      // start SMS timer button
      this.self().restartResendTimer(this.__resendCodeSMSBtn, this.tr("Via SMS"), retryAfter);
      // and reset email button
      this.__resendCodeEmailBtn.set({
        label: this.tr("Via email"),
        enabled: true
      })
    },

    restartEmailButton: function(retryAfter) {
      // start Email timer button
      this.self().restartResendTimer(this.__resendCodeEmailBtn, this.tr("Via email"), retryAfter);
      // and reset SMS button
      this.__resendCodeSMSBtn.set({
        label: this.tr("Via SMS"),
        enabled: true
      })
    },

    __validateCodeLogin: function() {
      this.__validateCodeBtn.setFetching(true);

      const validationCodeTF = this._form.getItems()["validationCode"];
      const validationCode = validationCodeTF.getValue();

      const loginFun = log => {
        this.__validateCodeBtn.setFetching(false);
        this.fireDataEvent("done", log.message);
      };

      const failFun = msg => {
        this.__validateCodeBtn.setFetching(false);
        // TODO: can get field info from response here
        msg = String(msg) || this.tr("Invalid code");
        validationCodeTF.setInvalidMessage(msg);

        osparc.FlashMessenger.logAs(msg, "ERROR");
      };

      if (this._form.validate()) {
        const manager = osparc.auth.Manager.getInstance();
        manager.validateCodeLogin(this.getUserEmail(), validationCode, loginFun, failFun, this);
      } else {
        this.__validateCodeBtn.setFetching(true);
      }
    },

    _onAppear: function() {
      const command = new qx.ui.command.Command("Enter");
      this.__validateCodeBtn.setCommand(command);
    },

    _onDisappear: function() {
      this.__validateCodeBtn.setCommand(null);
    }
  }
});
