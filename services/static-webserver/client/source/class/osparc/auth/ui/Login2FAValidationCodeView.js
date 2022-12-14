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


qx.Class.define("osparc.auth.ui.Login2FAValidationCodeView", {
  extend: osparc.auth.core.BaseAuthPage,

  properties: {
    userPhoneNumber: {
      check: "String",
      init: "+41-XXXXXXXXX",
      nullable: false,
      event: "changeUserPhoneNumber"
    },

    userEmail: {
      check: "String",
      init: "foo@mymail.com",
      nullable: false
    }
  },

  members: {
    __validateCodeTF: null,
    __validateCodeBtn: null,
    __resendCodeBtn: null,

    _buildPage: function() {
      const smsCodeDesc = new qx.ui.basic.Label();
      this.bind("userPhoneNumber", smsCodeDesc, "value", {
        converter: pNumber => this.tr("We just sent a 4-digit code to ") + pNumber
      });
      this.add(smsCodeDesc);

      const validateCodeTF = this.__validateCodeTF = new qx.ui.form.TextField().set({
        placeholder: this.tr("Type code"),
        required: true
      });
      this.add(validateCodeTF);
      this.addListener("appear", () => {
        validateCodeTF.focus();
        validateCodeTF.activate();
        osparc.auth.core.Utils.restartResendTimer(this.__resendCodeBtn, this.tr("Resend code"));
      });

      const validateCodeBtn = this.__validateCodeBtn = new osparc.ui.form.FetchButton(this.tr("Validate")).set({
        center: true,
        appearance: "strong-button"
      });
      validateCodeBtn.addListener("execute", () => this.__validateCodeLogin(), this);
      this.add(validateCodeBtn);

      const resendLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignY: "middle"
      }));
      const resendCodeDesc = new qx.ui.basic.Label().set({
        value: this.tr("Didn't receive the code?")
      });
      resendLayout.add(resendCodeDesc, {
        flex: 1
      });

      this.add(new qx.ui.core.Spacer(null, 20));
      const resendCodeBtn = this.__resendCodeBtn = new qx.ui.form.Button().set({
        label: this.tr("Resend code") + ` (60)`,
        enabled: false
      });
      resendLayout.add(resendCodeBtn, {
        flex: 1
      });
      resendCodeBtn.addListener("execute", () => {
        const msg = this.tr("Not yet implemented. Please, reload the page instead");
        osparc.component.message.FlashMessenger.getInstance().logAs(msg, "WARNING");
        // osparc.auth.ui.VerifyPhoneNumberView.restartResendTimer(this.__resendCodeBtn, this.tr("Resend code"));
      }, this);
      this.add(resendLayout);
    },

    __validateCodeLogin: function() {
      this.__validateCodeBtn.setFetching(true);

      const loginFun = log => {
        this.__validateCodeBtn.setFetching(false);
        this.fireDataEvent("done", log.message);
      };

      const failFun = msg => {
        this.__validateCodeBtn.setFetching(false);
        // TODO: can get field info from response here
        msg = String(msg) || this.tr("Invalid code");
        this.__validateCodeTF.set({
          invalidMessage: msg,
          valid: false
        });

        osparc.component.message.FlashMessenger.getInstance().logAs(msg, "ERROR");
      };

      const manager = osparc.auth.Manager.getInstance();
      manager.validateCodeLogin(this.getUserEmail(), this.__validateCodeTF.getValue(), loginFun, failFun, this);
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
