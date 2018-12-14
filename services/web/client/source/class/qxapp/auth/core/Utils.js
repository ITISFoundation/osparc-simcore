qx.Class.define("qxapp.auth.core.Utils", {
  type: "static",

  statics:
  {
    checkPasswordSecure:  function(password, itemForm) {
      const isValid = password !== null && password.length > 2;
      if (!isValid) {
        const msg = qx.locale.Manager.tr("Please enter a password at with least 3 characters.");
        itemForm.setInvalidMessage(msg);
      }
      return isValid;
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

    findGetParameter: function(parameterName) {
      let result = null;
      const params = window.location.search.substr(1).split("&");
      params.forEach(function(item) {
        let tmp = item.split("=");
        if (tmp[0] === parameterName) {
          result = decodeURIComponent(tmp[1]);
        }
      });
      return result;
    }
  }
});
