/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo (pcrespov)

************************************************************************ */

qx.Class.define("osparc.auth.core.Utils", {
  type: "static",

  statics: {
    passwordLengthValidator: function(value, item) {
      const valid = (value != null) && (value.length > 11);
      if (!valid) {
        item.setInvalidMessage("Please enter a password at with least 12 characters.");
      }
      return valid;
    },

    checkSamePasswords: function(passwordField1, passwordField2) {
      const isValid = passwordField1.getValue() == passwordField2.getValue();
      if (!isValid) {
        [passwordField1, passwordField2].forEach(pass => {
          pass.set({
            invalidMessage: qx.locale.Manager.tr("Passwords do not match"),
            valid: false
          });
        });
      }
      return isValid;
    },

    // https://en.wikipedia.org/wiki/E.164 '^\+[1-9]\d{4,14}$'
    phoneNumberValidator: function(phoneNumber, item) {
      const regEx = /^\+[1-9]\d{4,14}$/;
      const isValid = regEx.test(phoneNumber);
      item.set({
        invalidMessage: isValid ? "" : qx.locale.Manager.tr("Invalid phone number. Please [+][country code][phone number]"),
        valid: isValid
      });
      return isValid;
    },

    denylistEmailValidator: function(denylist) {
      return emailValue => {
        let errorMessage = "";
        qx.util.Validate.checkEmail(emailValue, null, errorMessage);
        // if the email check goes through, check it now against the denylist
        if (denylist) {
          denylist.forEach(reg => {
            const re = new RegExp(reg);
            if (re.test(emailValue)) {
              errorMessage = qx.locale.Manager.tr("Invalid email address.<br>Please register using your university email address");
              throw new qx.core.ValidationError("Validation Error", errorMessage);
            }
          })
        }
      };
    },

    checkEmail: function(emailValue) {
      // Same expression used in qx.util.Validate.checkEmail
      const reg = /^([A-Za-z0-9_\-.+])+@([A-Za-z0-9_\-.])+\.([A-Za-z]{2,})$/;
      return reg.test(emailValue);
    },

    /** Finds parameters in the fragment
     *
     * Expected fragment format as https://osparc.io#page=reset-password;code=123546
     * where fragment is #page=reset-password;code=123546
     */
    findParameterInFragment: function(parameterName) {
      let result = null;
      const params = window.location.hash.substr(1).split(";");
      params.forEach(function(item) {
        const tmp = item.split("=");
        if (tmp[0].includes(parameterName)) {
          result = decodeURIComponent(tmp[1]);
        }
      });
      return result;
    },

    removeParameterInFragment: function(parameterName) {
      let url = window.location.href;
      const value = osparc.auth.core.Utils.findParameterInFragment(parameterName);
      if (value) {
        const removeMe = parameterName + "=" + value;
        // In case the parameter has an ampersand in front
        url = url.replace(";" + removeMe, "");
        url = url.replace(removeMe, "");
        if (url.slice(-1) === "#") {
          // clean remaining character if all parameters were removed
          url = url.replace("#", "");
        }
        window.history.replaceState("", document.title, url);
      }
    },

    extractMessage: function(resp) {
      const defaultMessage = "";
      const retry = "parameters" in resp && "message" in resp["parameters"] ? resp["parameters"]["message"] : defaultMessage;
      return retry;
    },

    extractRetryAfter: function(resp) {
      const defaultRetry = 60;
      const retry = "parameters" in resp && "expiration_2fa" in resp["parameters"] ? resp["parameters"]["expiration_2fa"] : defaultRetry;
      return retry;
    }
  }
});
