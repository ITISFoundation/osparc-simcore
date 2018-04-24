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
      this._socket = new qxapp.wrappers.WebSocket("app");
      this._socket.connect();

      let win = new qx.ui.window.Window("Login");
      win.setLayout(new qx.ui.layout.VBox());

      let form = new qx.ui.form.Form();
      let userName = new qx.ui.form.TextField();
      // userName.setRequired(true);
      form.add(userName, "Name");
      let password = new qx.ui.form.PasswordField();
      // password.setRequired(true);
      form.add(password, "Password");
      let sendButton = new qx.ui.form.Button("Login");
      let scope = this;
      sendButton.addListener("execute", function() {
        if (form.validate()) {
          if (qxapp.utils.Utils.inHouse(form.getGroups()[0].items[1].getValue())) {
            win.close();
            this._layoutManager = new qxapp.layout.LayoutManager();
            doc.add(this._layoutManager);
          }
        }
      }, scope);
      form.addButton(sendButton);

      win.add(new qx.ui.form.renderer.Single(form));
;
      win.setShowMinimize(false);
      win.setShowMaximize(false);
      win.setShowClose(false);
      win.open();
      this.getRoot().add(win, {
        left:400,
        top:400
      });
    }
  }
});
