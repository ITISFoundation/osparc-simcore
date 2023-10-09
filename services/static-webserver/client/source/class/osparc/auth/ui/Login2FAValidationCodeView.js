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
    userPhoneNumber: {
      check: "String",
      init: null,
      nullable: true,
      event: "changeUserPhoneNumber"
    },

    userEmail: {
      check: "String",
      init: "foo@mymail.com",
      nullable: false
    }
  },

  members: {
    __validateCodeBtn: null,
    __resendCodeSMSBtn: null,
    __resendCodeEmailBtn: null,

    _buildPage: function() {
      const introText = new qx.ui.basic.Label();
      const justSentText = this.tr("We just sent a 6-digit code to ");
      this.bind("userPhoneNumber", introText, "value", {
        converter: pNumber => justSentText + (pNumber ? pNumber : this.getUserEmail())
      });
      this.add(introText);

      // form
      const validateCodeTF = new qx.ui.form.TextField().set({
        required: true
      });
      this._form.add(validateCodeTF, this.tr("Type code"), null, "validationCode");
      this.addListener("appear", () => {
        validateCodeTF.focus();
        validateCodeTF.activate();
        this.__restartTimers();
      });

      Object.values(this._form.getItems()).forEach(formItem => formItem.setWidth(osparc.auth.core.BaseAuthPage.FORM_WIDTH));
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

      const resendCodeSMSBtn = this.__resendCodeSMSBtn = new osparc.ui.form.FetchButton().set({
        label: this.tr("Via SMS") + ` (60)`,
        enabled: false
      });
      this.bind("userPhoneNumber", resendCodeSMSBtn, "visibility", {
        converter: pNumber => pNumber ? "visible" : "excluded"
      });
      resendButtonsLayout.add(resendCodeSMSBtn, {
        flex: 1
      });
      resendCodeSMSBtn.addListener("execute", () => {
        resendCodeSMSBtn.setFetching(true);
        osparc.auth.Manager.getInstance().resendCodeViaSMS(this.getUserEmail())
          .then(data => {
            resendCodeSMSBtn.setFetching(false);
            osparc.FlashMessenger.logAs(data.reason, "INFO");
            introText.setValue(justSentText + this.getUserPhoneNumber());
            this.__restartTimers();
          })
          .catch(err => {
            resendCodeSMSBtn.setFetching(false);
            osparc.FlashMessenger.logAs(err.message, "ERROR");
          });
      }, this);

      const resendCodeEmailBtn = this.__resendCodeEmailBtn = new osparc.ui.form.FetchButton().set({
        label: this.tr("Via email") + ` (60)`,
        enabled: false
      });
      resendButtonsLayout.add(resendCodeEmailBtn, {
        flex: 1
      });
      resendCodeEmailBtn.addListener("execute", () => {
        resendCodeEmailBtn.setFetching(true);
        osparc.auth.Manager.getInstance().resendCodeViaEmail(this.getUserEmail())
          .then(data => {
            resendCodeEmailBtn.setFetching(false);
            osparc.FlashMessenger.logAs(data.reason, "INFO");
            introText.setValue(justSentText + this.getUserEmail());
            this.__restartTimers();
          })
          .catch(err => {
            resendCodeEmailBtn.setFetching(false);
            osparc.FlashMessenger.logAs(err.message, "ERROR");
          });
      }, this);
      this.add(resendLayout);
    },

    __restartTimers: function() {
      if (this.getUserPhoneNumber()) {
        osparc.auth.core.Utils.restartResendTimer(this.__resendCodeSMSBtn, this.tr("Via SMS"));
      }
      osparc.auth.core.Utils.restartResendTimer(this.__resendCodeEmailBtn, this.tr("Via email"));
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

        osparc.FlashMessenger.getInstance().logAs(msg, "ERROR");
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
