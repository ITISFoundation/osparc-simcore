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


qx.Class.define("osparc.auth.ui.SMSCodeView", {
  extend: osparc.auth.core.BaseAuthPage,

  members: {
    __form: null,
    __validateCodeBtn: null,
    __resendCodeBtn: null,

    _buildPage: function() {
      this.__form = new qx.ui.form.Form();

      const smsCodeDesc = new qx.ui.basic.Label().set({
        value: this.tr("We just sent a 4-digit code to +41-XXXXX1766")
      });
      this.add(smsCodeDesc);

      const smsCode = new qx.ui.form.TextField().set({
        placeholder: this.tr("Type code"),
        required: true
      });
      this.add(smsCode);
      this.addListener("appear", () => {
        smsCode.focus();
        smsCode.activate();
        this.__restartTimer();
      });
      this.__form.add(smsCode, "", null, "smsCode", null);

      const validateCodeBtn = this.__validateCodeBtn = new osparc.ui.form.FetchButton(this.tr("Validate")).set({
        center: true,
        appearance: "strong-button"
      });
      validateCodeBtn.addListener("execute", () => this.__validateCode(), this);
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
      resendCodeBtn.addListener("execute", () => this.__resendCode(), this);
      this.add(resendLayout);
    },

    __validateCode: function() {
      this.__validateCodeBtn.setFetching(true);

      const smsCode = this.__form.getItems().smsCode;

      if (smsCode.getValue() === "8004") {
        this.__validateCodeBtn.setFetching(false);
        this.fireDataEvent("done");
      } else {
        this.__validateCodeBtn.setFetching(false);
        const msg = this.tr("Invalid code");
        smsCode.set({
          invalidMessage: msg,
          valid: false
        });
        osparc.component.message.FlashMessenger.getInstance().logAs(msg, "ERROR");
      }
    },

    __restartTimer: function() {
      let count = 60;
      const refreshIntervalId = setInterval(() => {
        if (count > 0) {
          count--;
        } else {
          clearInterval(refreshIntervalId);
        }
        this.__resendCodeBtn.set({
          label: count > 0 ? this.tr("Resend code") + ` (${count})` : this.tr("Resend code"),
          enabled: count === 0
        });
      }, 1000);
    },

    __resendCode: function() {
      this.__restartTimer();
    }
  }
});
