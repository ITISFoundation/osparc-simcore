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
      }

      if (qx.core.Environment.get("dev.enableFakeSrv")) {
        console.debug("Fake server enabled");
        qxapp.dev.fake.srv.restapi.User;
        qxapp.dev.fake.srv.restapi.Authentication;
      }

      // openning web socket
      qxapp.wrappers.WebSocket.getInstance().connect();

      this.start();
    },

    /**
     * This is controlled entry-point to start the application
    */
    start: function() {
      let isLogged = qxapp.auth.Store.isLoggedIn();

      if (qx.core.Environment.get("dev.disableLogin")) {
        console.warn("Login page was disabled", "Starting main application ...");
        isLogged = true;
      }

      if (isLogged) {
        this.__startDesktop();
      } else {
        this.__layoutManager = null;
        let page = new qxapp.auth.LoginPage();
        // event : successfully logged it ... then application decides
        page.show();
      }
    },

    /**
     * Resets session and restarts
    */
    logout: function() {
      qxapp.auth.Store.resetToken();
      this.getRoot().removeAll();
      this.start();
    },

    /**
     * Desktop correspond to the main application's pages
    */
    __startDesktop: function() {
      this.__layoutManager = new qxapp.desktop.LayoutManager();

      this.getRoot().add(this.__layoutManager, {
        left: "0%",
        top: "0%",
        height: "100%",
        width: "100%"
      });
    }

  }
});
