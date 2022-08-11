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


qx.Class.define("osparc.auth.ui.RegisterSMSCodeView", {
  extend: osparc.auth.core.BaseAuthPage,

  properties: {
    userEmail: {
      check: "String",
      init: "foo@mymail.com",
      nullable: false
    }
  },

  members: {
    __form: null,
    __validateCodeBtn: null,
    __resendCodeBtn: null,

    _buildPage: function() {
      this.__form = new qx.ui.form.Form();

      const phoneNumberVerifyLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      const phoneNumber = new qx.ui.form.TextField().set({
        required: true,
        placeholder: this.tr("Type your phone number")
      });
      phoneNumberVerifyLayout.add(phoneNumber, {
        flex: 1
      });
      const verifyPhoneBtn = new qx.ui.form.Button(this.tr("Verify")).set({
        minWidth: 80
      });
      phoneNumberVerifyLayout.add(verifyPhoneBtn);
      this.add(phoneNumberVerifyLayout);

      const smsValidationLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      const validationCode = new qx.ui.form.TextField().set({
        placeholder: this.tr("Type the SMS code"),
        enabled: false
      });
      smsValidationLayout.add(validationCode, {
        flex: 1
      });
      const validateCodeBtn = new osparc.ui.form.FetchButton(this.tr("Validate")).set({
        minWidth: 80,
        enabled: false
      });
      smsValidationLayout.add(validateCodeBtn);
      this.add(smsValidationLayout);


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
          osparc.auth.Manager.getInstance().verifyPhoneNumber(this.getUserEmail(), phoneNumber.getValue())
            .then(data => {
              osparc.component.message.FlashMessenger.logAs(data.message, "INFO");
              validationCode.setEnabled(true);
              validateCodeBtn.setEnabled(true);
            })
            .catch(err => {
              osparc.component.message.FlashMessenger.logAs(err.message, "ERROR");
              phoneNumber.setEnabled(true);
            });
        }
      });

      validateCodeBtn.addListener("execute", () => {
        validateCodeBtn.setFetching(true);
        osparc.auth.Manager.getInstance().validateCodeRegister(this.getUserEmail(), phoneNumber.getValue(), validationCode.getValue())
          .then(data => {
            osparc.component.message.FlashMessenger.logAs(data.message, "INFO");
            validateCodeBtn.setFetching(false);
            validationCode.setEnabled(false);
            validateCodeBtn.setEnabled(false);
            validateCodeBtn.setIcon("@FontAwesome5Solid/check/12");
            this.fireDataEvent("done", data.message);
          })
          .catch(err => {
            osparc.component.message.FlashMessenger.logAs(err.message, "ERROR");
            validateCodeBtn.setFetching(false);
          });
      });
    }
  }
});
