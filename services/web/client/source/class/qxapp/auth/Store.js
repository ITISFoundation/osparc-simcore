qx.Class.define("qxapp.auth.Store", {
  type: "static",
  statics:
  {
    AUTHENTICATION_TOKEN: null,

    setToken: function(token) {
      const auth = new qx.io.request.authentication.Basic(token, null);
      qxapp.auth.BaseAuthPage.AUTHENTICATION_TOKEN = auth;
    }
  }
});
