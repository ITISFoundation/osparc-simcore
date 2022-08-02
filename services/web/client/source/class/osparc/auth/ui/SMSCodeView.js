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

    _buildPage: function() {
      this.__form = new qx.ui.form.Form();

      const smsCode = new qx.ui.form.TextField().set({
        placeholder: this.tr("Type code"),
        required: true
      });
      this.add(smsCode);
      this.addListener("appear", () => {
        smsCode.focus();
        smsCode.activate();
      });
      this.__form.add(smsCode, "", null, "smsCode", null);

      const validateCodeBtn = this.__validateCodeBtn = new osparc.ui.form.FetchButton(this.tr("Validate")).set({
        center: true,
        appearance: "strong-button"
      });
      validateCodeBtn.addListener("execute", () => this.__validateCode(), this);
      this.add(validateCodeBtn);
    },

    __validateCode: function() {
      this.__validateCodeBtn.setFetching(true);

      const smsCode = this.__form.getItems().smsCode;

      const successFun = log => {
        this.__validateCodeBtn.setFetching(false);
        this.fireDataEvent("done", log.message);
      };

      const failFun = msg => {
        this.__validateCodeBtn.setFetching(false);
        msg = String(msg) || this.tr("Invalid code");
        smsCode.set({
          invalidMessage: msg,
          valid: false
        });

        osparc.component.message.FlashMessenger.getInstance().logAs(msg, "ERROR");
      };

      const manager = osparc.auth.Manager.getInstance();
      manager.login(smsCode.getValue(), smsCode.getValue(), successFun, failFun, this);
    }
  }
});
