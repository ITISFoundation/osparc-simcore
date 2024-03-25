/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.CookieExpirationTracker", {
  extend: qx.core.Object,
  type: "singleton",

  statics: {
    PERMANENT_WARN_IN_ADVANCE: 60*60, // Show Ribbon Permanent Message 1h in advance
    LOG_OUT_BEFORE_EXPIRING: 60 // Log user out 1' in before expiring
  },

  members: {
    startTracker: function() {
      const cookieMaxAge = osparc.store.StaticInfo.getInstance().getCookieMaxAge();
      if (cookieMaxAge) {
        const showMessageIn = Math.max(cookieMaxAge - this.self().PERMANENT_WARN_IN_ADVANCE, 0);
        setTimeout(() => this.__showFlashMessage(), showMessageIn*1000);

        const logOutIn = Math.max(cookieMaxAge - this.self().LOG_OUT_BEFORE_EXPIRING, 0);
        setTimeout(() => this.__logoutUser(), logOutIn*1000);
      }
    },

    __showFlashMessage: function() {
      const text = qx.locale.Manager.tr("Your session will expire in 1 hour.<br>Please, log out and log in again.");
      osparc.FlashMessenger.getInstance().logAs(text, "WARNING", (this.self().PERMANENT_WARN_IN_ADVANCE-this.self().LOG_OUT_BEFORE_EXPIRING)*1000);
    },

    __logoutUser: function() {
      const text = qx.locale.Manager.tr("Session expired");
      qx.core.Init.getApplication().logout(text);
    }
  }
});
