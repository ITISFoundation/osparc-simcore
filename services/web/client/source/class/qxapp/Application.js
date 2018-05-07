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

/* global qxapp */
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
    _socket: null,
    _layoutManager: null,

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
        // support additional cross-browser console. Press F7 to toggle visibility
        qx.log.appender.Console;
      }

      /*
      -------------------------------------------------------------------------
        Below is your actual application code...
      -------------------------------------------------------------------------
      */

      qx.locale.Manager.getInstance().setLocale("en");
      qx.locale.Manager.getInstance().addListener("changeLocale", function(e) {
        qx.locale.Manager.getInstance().setLocale(e.getData());
      }, this);

      // Document is the application root
      let doc = this.getRoot();

      // openning web socket
      this._socket = qxapp.wrappers.WebSocket.getInstance();
      this._socket.connect();

      let login = new qxapp.login.Login();
      login.addListener("login", function(e) {
        // FIXME: For the moment, password is not checked
        // if (e.getData() === true) {
        this._layoutManager = new qxapp.layout.LayoutManager();
        doc.remove(login);
        doc.add(this._layoutManager);
        // }
      });

      doc.set({
        backgroundColor: "dark-blue"
      });
      doc.add(login, {
        left: "10%",
        top: "10%",
        height: "30%"
      });
    }
  }
});
