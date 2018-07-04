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
        // FIXME: For the moment, password is not checked
        // if (e.getData() === true) {
        this.__layoutManager = new qxapp.desktop.LayoutManager();
        doc.remove(login);
        doc.add(this.__layoutManager, {
          left: "0%",
          top: "0%",
          height: "100%",
          width: "100%"
        });
        // }
      }, this);

      doc.add(login, {
        left: "10%",
        top: "10%",
        height: "30%"
      });
      /** a little ajv test */
      let loader = new qx.io.request.Xhr("/resource/qxapp/node-meta-v0.0.1.json");
      loader.addListener("success", e => {
        let data = e.getTarget().getResponse();
        let ajv = new qxapp.wrappers.Ajv(data);
        let good = ajv.validate({
          key: "service/computational/sleeper",
          tag: "0.0.0-alpha",
          name: "a little test node",
          description: "just the bare minimum",
          authors: [
            {
              name: "Tobias Oetiker",
              email: "oetiker@itis.ethz.ch"
            }
          ],
          contact: "oetiker@itis.ethz.ch",
          inputs: {},
          outputs: {}
        });
        console.log("validation result good", good);
        let bad = ajv.validate({
          key: "service/computational/sleeper",
          tag: "d0.0.0-alpha",
          name: "a little test node",
          description: "just the bare minimum",
          authors: [
          ],
          contact: "oetiker@itis.ethz.ch",
          inputs: {},
          outputs: {}
        });
        console.log("validation result bad", bad);
      });
      loader.send();
    }
  }
});
