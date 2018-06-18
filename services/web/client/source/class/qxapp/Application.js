/* ************************************************************************

   Copyright: 2018 undefined

   License: MIT license

   Authors: undefined

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

  /*
  *****************************************************************************
     MEMBERS
  *****************************************************************************
  */

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
          qxapp.dev.fakesrv.restapi.User;
          qxapp.dev.fakesrv.restapi.Authentication;
        }
      }

      /*
      TODO: change name of app: osparc instead of qxapp

      */
      // Document is the application root
      let doc = this.getRoot();

      // openning web socket
      qxapp.wrappers.WebSocket.getInstance().connect();

      let login = new qxapp.components.login.Login();
      login.addListener("login", function(e) {
        if (e.getData() === true) {
          // TODO: need to init user-id and token in data layer

          this.__layoutManager = new qxapp.desktop.LayoutManager();
          doc.remove(login);
          doc.add(this.__layoutManager, {
            left: "0%",
            top: "0%",
            height: "100%",
            width: "100%"
          });
        } else {
          // TODO: some kind of notification as in
          //  http://www.qooxdoo.org/5.0.1/pages/website/tutorial_web_developers.html
          // flash("Invalid user name or password");
          console.log("Invalid user or password.");
        }
      }, this);

      // TOOD: center in document
      doc.add(login, {
        left: "10%",
        top: "10%",
        height: "30%"
      });
    }
  }
});
