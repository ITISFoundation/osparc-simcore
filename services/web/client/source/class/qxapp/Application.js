/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Tobias Oetiker (oetiker)
     * Pedro Crespo (pcrespov)

************************************************************************ */

/**
 * This is the main application class of "qxapp"
 *
 * @asset(qxapp/*)
 */

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
      this.__preventAutofillBrowserSyles();

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

      this.__initRouting();
    },

    __initRouting: function() {
      // TODO: PC -> IP consider regex for uuid, i.e. /[0-9a-fA-F]{8}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{12}/ ???
      const urlFragment = qxapp.utils.Utils.parseURLFragment();
      if (urlFragment.nav && urlFragment.nav.length) {
        if (urlFragment.nav[0] === "study" && urlFragment.nav.length > 1) {
          // Route: /#/study/{id}
          qxapp.utils.Utils.cookie.deleteCookie("user");
          qxapp.auth.Manager.getInstance().validateToken(() => this.__loadMainPage(urlFragment.nav[1]), this.__loadLoginPage, this);
        } else if (urlFragment.nav[0] === "registration" && urlFragment.params && urlFragment.params.invitation) {
          // Route: /#/registration/?invitation={token}
          qxapp.utils.Utils.cookie.deleteCookie("user");
          this.__restart();
        }
        else {
          // this.load404();
          console.error("URL fragment format not recognized.")
        }
      } else {
        this.__restart();
      }
    },

    __restart: function() {
      let isLogged = qxapp.auth.Manager.getInstance().isLoggedIn();

      if (qx.core.Environment.get("dev.disableLogin")) {
        console.warn("Login page was disabled", "Starting main application ...");
        isLogged = true;
      }

      if (isLogged) {
        this.__loadMainPage();
      } else {
        qxapp.auth.Manager.getInstance().validateToken(this.__loadMainPage, this.__loadLoginPage, this);
      }
    },

    __loadLoginPage: function() {
      this.__disconnectWebSocket();
      const view = new qxapp.auth.LoginPage();
      view.addListener("done", function(msg) {
        this.__restart();
      }, this);
      this.__loadView(view, {
        top: "10%",
        bottom: 0,
        left: 0,
        right: 0
      });
    },

    __loadMainPage: function(studyId) {
      this.__connectWebSocket();
      this.__loadView(new qxapp.desktop.MainPage(studyId), {
        top: 0,
        bottom: 0,
        left: 0,
        right: 0
      });
    },

    __loadView: function(view, options) {
      this.assert(view!==null);
      // Update root document and currentness
      let doc = this.getRoot();
      if (doc.hasChildren() && this.__current) {
        doc.remove(this.__current);
        // this.__current.destroy();
      }
      doc.add(view, options);
      this.__current = view;
      // Clear URL
      window.history.replaceState(null, "", "/");
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
      qxapp.wrapper.WebSocket.getInstance().connect();
    },

    __disconnectWebSocket: function() {
      // open web socket
      qxapp.wrapper.WebSocket.getInstance().disconnect();
    },

    __preventAutofillBrowserSyles: function() {
      const stylesheet = qx.ui.style.Stylesheet.getInstance();
      if (qx.bom.client.Browser.getName() === "chrome" && qx.bom.client.Browser.getVersion() >= 71) {
        stylesheet.addRule(
          "input:-internal-autofill-previewed," +
          "input:-internal-autofill-selected," +
          "textarea:-internal-autofill-previewed," +
          "textarea:-internal-autofill-selected," +
          "select:-internal-autofill-previewed," +
          "select:-internal-autofill-selected",

          "transition: background-color 0s linear 100000s, color 0s linear 100000s"
        );
      } else if (qx.bom.client.Engine.getName() === "webkit") {
        stylesheet.addRule(
          "input:-webkit-autofill," +
          "input:-webkit-autofill:hover," +
          "input:-webkit-autofill:focus," +
          "textarea:-webkit-autofill," +
          "textarea:-webkit-autofill:hover," +
          "textarea:-webkit-autofill:focus," +
          "select:-webkit-autofill," +
          "select:-webkit-autofill:hover," +
          "select:-webkit-autofill:focus",

          "transition: background-color 0s linear 100000s, color 0s linear 100000s"
        );
      }
    }
  }
});
