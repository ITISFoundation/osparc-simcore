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

      if (qx.core.Environment.get("dev.enableFakeSrv")) {
        console.debug("Fake server enabled");
        qxapp.dev.fake.srv.restapi.User;
        qxapp.dev.fake.srv.restapi.Authentication;
      }

      // openning web socket
      qxapp.wrappers.WebSocket.getInstance().connect();

      // Setting up auth manager
      qxapp.auth.Manager.getInstance().addListener("logout", function() {
        this.__restart();
      }, this);

      this.__restart();
      this.__schemaCheck();
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
        view = new qxapp.desktop.LayoutManager();

        options = {
          left: 0,
          top: 0,
          height: "100%",
          width: "100%"
        };
      } else {
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

    __schemaCheck: function() {
      /** a little ajv test */
      let nodeCheck = new qx.io.request.Xhr("/resource/qxapp/node-meta-v0.0.1.json");
      nodeCheck.addListener("success", e => {
        let data = e.getTarget().getResponse();
        try {
          let ajv = new qxapp.wrappers.Ajv(data);
          let map = qxapp.data.Store.getInstance().getServices();
          for (let key in map) {
            let check = ajv.validate(map[key]);
            console.log("services validation result " + key + ":", check);
          }
        } catch (err) {
          console.error(err);
        }
      });
      nodeCheck.send();
      let projectCheck = new qx.io.request.Xhr("/resource/qxapp/project-v0.0.1.json");
      projectCheck.addListener("success", e => {
        let data = e.getTarget().getResponse();
        try {
          let ajv = new qxapp.wrappers.Ajv(data);
          let list = qxapp.data.Store.getInstance().getProjectList();
          list.forEach((project, i) => {
            let check = ajv.validate(project);
            console.log("project validation result " + i + ":", check);
          });
        } catch (err) {
          console.error(err);
        }
      });
      projectCheck.send();
    }

  }
});
