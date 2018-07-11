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
      let isLogged = qxapp.auth.Manager.getInstance().isLoggedIn();

      if (qx.core.Environment.get("dev.disableLogin")) {
        console.warn("Login page was disabled", "Starting main application ...");
        isLogged = true;
      }

      if (isLogged) {
        this.__startDesktopView();
      } else {
        let login = new qxapp.auth.LoginPage();

        login.addListener("done", function(msg) {
          // if msg, flash it
          this.start();
        }, this);

        login.addListener("toReset", function(e) {
          let page = new qxapp.auth.ResetPassPage();
          page.addListener("done", function(msg) {
            this.start();
          }, this);
          this.__startAuthView(page);
        }, this);

        login.addListener("toRegister", function(e) {
          let page = new qxapp.auth.RegistrationPage();
          page.addListener("done", function(msg) {
            this.start();
          }, this);
          this.__startAuthView(page);
        }, this);

        this.__startAuthView(login);
      }
    },

    /**
     * Resets session and restarts
    */
    logout: function() {
      qxapp.auth.Manager.getInstance().logout();
      this.start();
    },

    /**
     * Desktop correspond to the main application's pages
    */
    __startDesktopView: function() {
      this.__layoutManager = new qxapp.desktop.LayoutManager();
      this.__current = this.__layoutManager;

      this.getRoot().add(this.__layoutManager, {
        left: "0%",
        top: "0%",
        height: "100%",
        width: "100%"
      });
    },

    __startAuthView: function(page) {
      // creates a page container
      let layout = new qx.ui.layout.Grid();
      layout.setRowFlex(0, 1);
      layout.setColumnFlex(0, 1);

      let container = new qx.ui.container.Composite(layout);
      container.add(page, {
        row:0,
        column:0
      });

      // removes current page
      let doc = this.getRoot();
      if (doc.hasChildren() && this.__current) {
        doc.remove(this.__current);
        this.__current.destroy();
      }

      // adds new page
      doc.add(container, {
        top: "10%",
        bottom: 0,
        left: 0,
        right: 0
      });
      this.__current = container;
    }



  }
});
