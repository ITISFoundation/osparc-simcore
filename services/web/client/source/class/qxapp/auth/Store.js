
qx.Class.define("qxapp.auth.Store", {
  type: "static",
  statics:
  {
    TOKEN: null,

    setToken: function(token) {
      const auth = new qx.io.request.authentication.Basic(token, null);
      qxapp.auth.BaseAuthPage.TOKEN = auth;
    },

    resetToken: function() {
      qxapp.auth.BaseAuthPage.TOKEN = null;
    },

    isLoggedIn: function() {
      const auth = qxapp.auth.BaseAuthPage.TOKEN;
      // TODO: how to store this localy?? See http://www.qooxdoo.org/devel/pages/data_binding/stores.html#offline-store
      // TODO: check if expired??
      // TODO: request server if token is still valid (e.g. expired, etc)
      return auth !== null && auth instanceof qx.io.request.authentication.Basic;
    }
  }
});
