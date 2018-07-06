/* ************************************************************************

   Copyright: 2018 undefined

   License: MIT license

   Authors: undefined
TODO: change name of app: osparc instead of qxapp
************************************************************************ */

/**
 * This is the main application class of "app"
 *
 * @asset(qxapp/*)
 */

/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.Application", {
  extend: qx.application.Standalone,
  include: [qx.locale.MTranslation],

  members:
  {
    __layoutManager: null,

    /**
     * This method contains the initial application code and gets called
     * during startup of the application
     */
    main: function() {
      // Call super class
      this.base();

      // Enable logging in debug variant
      if (qx.core.Environment.get("qx.debug")) {
        // support native logging capabilities, e.g. Firebug for Firefox
        qx.log.appender.Native;

        if (qx.core.Environment.get("dev.enableFakeSrv")) {
          console.debug("Fake server enabled");
          qxapp.dev.fake.srv.restapi.User;
          qxapp.dev.fake.srv.restapi.Authentication;
        }
      }

      // openning web socket
      qxapp.wrappers.WebSocket.getInstance().connect();

      this.__startDesktop();
      // FIXME: PC check how to enable url parameters when served with python server
      // if (qx.core.Environment.get("dev.disableLogin")) {
      //   console.debug("Login was disabled");
      //   this.__startDesktop();
      // } else {
      //   this.__startLogin();
      // }
    },

    __startDesktop: function() {
      this.__layoutManager = new qxapp.desktop.LayoutManager();
      this.getRoot().add(this.__layoutManager, {
        left: "0%",
        top: "0%",
        height: "100%",
        width: "100%"
      });
    },

    __startLogin: function() {
      let login = new qxapp.components.login.Login();

      login.addListener("login", function(e) {
        // TODO: need to init user-id and token in data layer
        if (e.getData() === true) {
          this.getRoot().remove(login);
          this.__startDesktop();
        } else {
          console.log("Invalid user or password.");
          // TODO: some kind of notification as in
          //  http://www.qooxdoo.org/5.0.1/pages/website/tutorial_web_developers.html
          // flash("Invalid user name or password");
        }
      }, this);

      // TODO: center in document qx.ui.layout.Canvas
      this.getRoot().add(login, {
        left: "10%",
        top: "10%",
        height: "30%"
      });
    }
  }
});
