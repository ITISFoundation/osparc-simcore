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
  include: [
    qx.locale.MTranslation
  ],

  members:
  {
    __current: null,

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

      // alert the users that they are about to navigate away
      // from osparc. unfortunately it is not possible
      // to provide our own message here
      window.addEventListener("beforeunload", e => {
        // Cancel the event as stated by the standard.
        e.preventDefault();
        // Chrome requires returnValue to be set.
        e.returnValue = "";
      });
      if (qx.core.Environment.get("dev.enableFakeSrv")) {
        console.debug("Fake server enabled");
        qxapp.dev.fake.srv.restapi.User;
        qxapp.dev.fake.srv.restapi.Authentication;
      }

      // Setting up auth manager
      qxapp.auth.Manager.getInstance().addListener("logout", function() {
        this.__restart();
      }, this);

      this.__restart();
    },

    __restart: function() {
      let isLogged = qxapp.auth.Manager.getInstance().isLoggedIn();

      if (qx.core.Environment.get("dev.disableLogin")) {
        console.warn("Login page was disabled", "Starting main application ...");
        isLogged = true;
      }

      let view = null;
      let options = null;

      if (isLogged) {
        this.__connectWebSocket();

        view = new qxapp.desktop.LayoutManager();

        options = {
          left: 0,
          top: 0,
          height: "100%",
          width: "100%"
        };
      } else {
        this.__disconnectWebSocket();

        view = new qxapp.auth.AuthView();
        view.addListener("done", function(msg) {
          this.__restart();
        }, this);

        options ={
          top: "10%",
          bottom: 0,
          left: 0,
          right: 0
        };
      }

      this.assert(view!==null);
      // Update root document and currentness
      let doc = this.getRoot();
      if (doc.hasChildren() && this.__current) {
        doc.remove(this.__current);
        // this.__current.destroy();
      }
      doc.add(view, options);
      this.__current = view;
    },

    /**
     * Resets session and restarts
    */
    logout: function() {
      qxapp.auth.Manager.getInstance().logout();
      this.__restart();
    },

    __connectWebSocket: function() {
      // open web socket
      qxapp.wrappers.WebSocket.getInstance().connect();
    },

    __disconnectWebSocket: function() {
      // open web socket
      qxapp.wrappers.WebSocket.getInstance().disconnect();
    }
  }
});
