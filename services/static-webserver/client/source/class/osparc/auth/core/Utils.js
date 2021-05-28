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

  statics:
  {
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
        if (tmp[0] === parameterName) {
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
        // In case the parameterhas an ampersand in front
        url = url.replace(";" + removeMe, "");
        url = url.replace(removeMe, "");
        if (url.slice(-1) === "#") {
          // clean remaining character if all parameters were removed
          url = url.replace("#", "");
        }
        window.history.replaceState("", document.title, url);
      }
    }
  }
});
