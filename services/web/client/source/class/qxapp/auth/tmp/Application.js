/**
 * This is the main application class of "auth"
 *
 * @asset(auth/*)
 *
 */

qx.Class.define("auth.Application", {
  extend: qx.application.Standalone,

  members: {
    /**
     * This method contains the initial application code and gets called
     * during startup of the application
     *
     * @lint ignoreDeprecated(alert)
     */
    main: function() {
      // Call super class
      this.base(arguments);

      // Enable logging in debug variant
      if (qx.core.Environment.get("qx.debug")) {
        if (qx.core.Environment.get("auth.mockBackend")) {
          console.debug("Initializing FakeServer ...");
          auth.dev.RestAPI;
          auth.dev.Auth;
        }
      }

      var root = this.getRoot();
      root.set({
        backgroundColor: "#00284d"
      });

      this.restart();

      // this.__demo(root);
    },

    restart: function() {
      this.request("type=check", function(success) {
        var page = null;
        if (success) {
          page = new qxapp.auth.MainPage();
        } else {
          page = new qxapp.auth.LoginPage();
        }
        page.show();
      }, this);
    },

    request: function(str, cbk, ctx) {
      var req = new qx.io.request.Xhr("api/auth", "GET");
      req.setRequestData(str);
      req.addListener("success", function(e, x, y) {
        var request = e.getTarget();
        var response = request.getResponse();
        cbk.call(ctx, (response == "true"));
      }, this);

      req.send();
    },

    __demo: function(root) {
      /**
       *  Demo #1
       *
       */
      // root is configured as a Canvas here
      root.set({
        backgroundColor: "#00284d"
      });

      var widget = new qx.ui.container.Composite(new qx.ui.layout.Dock()).set(
        {
          // decorator: "main",
          allowGrowX: false
        });

      var loginPage = new qxapp.auth.login.LoginPage();
      loginPage.addListener("login", function(e) {
        if (e.getData() == true) {
          alert("Logged in!");
        }
      }, this);

      widget.add(loginPage, {
        edge: "center"
      });
      root.add(widget, {
        left: "0%",
        top: "0%",
        right: "0%",
        bottom: "0%",
        width: "0%",
        height: "0%"
      });
    }
  }
});
