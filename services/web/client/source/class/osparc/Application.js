/* ************************************************************************

   osparc - the simcore frontend

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
 * This is the main application class of "osparc"
 *
 * @asset(osparc/*)
 * @asset(common/common.css)
 */

qx.Class.define("osparc.Application", {
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

      const webSocket = osparc.wrapper.WebSocket.getInstance();
      webSocket.addListener("connect", () => {
        osparc.io.WatchDog.getInstance().setOnLine(true);
      });
      webSocket.addListener("disconnect", () => {
        osparc.io.WatchDog.getInstance().setOnLine(false);
      });
      webSocket.addListener("logout", e => {
        this.logout();
      });
      // alert the users that they are about to navigate away
      // from osparc. unfortunately it is not possible
      // to provide our own message here
      window.addEventListener("beforeunload", e => {
        if (webSocket.connected) {
          // Cancel the event as stated by the standard.
          e.preventDefault();
          // Chrome requires returnValue to be set.
          e.returnValue = "";
        }
      });
      if (qx.core.Environment.get("dev.enableFakeSrv")) {
        console.debug("Fake server enabled");
        osparc.dev.fake.srv.restapi.User;
        osparc.dev.fake.srv.restapi.Authentication;
      }

      // Setting up auth manager
      osparc.auth.Manager.getInstance().addListener("logout", function() {
        this.__restart();
      }, this);

      this.__initRouting();
      this.__loadCommonCss();
    },

    __initRouting: function() {
      const urlFragment = osparc.utils.Utils.parseURLFragment();
      if (urlFragment.nav && urlFragment.nav.length) {
        if (urlFragment.nav[0] === "study" && urlFragment.nav.length > 1) {
          // Route: /#/study/{id}
          osparc.utils.Utils.cookie.deleteCookie("user");
          osparc.auth.Manager.getInstance().validateToken(() => this.__loadMainPage(urlFragment.nav[1]), this.__loadLoginPage, this);
        } else if (urlFragment.nav[0] === "registration" && urlFragment.params && urlFragment.params.invitation) {
          // Route: /#/registration/?invitation={token}
          osparc.utils.Utils.cookie.deleteCookie("user");
          this.__restart();
        } else if (urlFragment.nav[0] === "reset-password" && urlFragment.params && urlFragment.params.code) {
          // Route: /#/reset-password/?code={resetCode}
          osparc.utils.Utils.cookie.deleteCookie("user");
          this.__restart();
        }
      } else if (urlFragment.params) {
        if (urlFragment.params.registered) {
          // Route: /#/?registered=true
          osparc.utils.Utils.cookie.deleteCookie("user");
          this.__restart();
        } else {
          // this.load404();
          console.error("URL fragment format not recognized.");
        }
      } else {
        this.__restart();
      }
    },

    __restart: function() {
      let isLogged = osparc.auth.Manager.getInstance().isLoggedIn();

      if (qx.core.Environment.get("dev.disableLogin")) {
        console.warn("Login page was disabled", "Starting main application ...");
        isLogged = true;
      }

      if (isLogged) {
        this.__loadMainPage();
      } else {
        // Reset store (cache)
        osparc.store.Store.getInstance().invalidate();

        osparc.auth.Manager.getInstance().validateToken(data => {
          if (data.role === "Guest") {
            // Logout a guest trying to access the Dashboard
            osparc.auth.Manager.getInstance().logout();
          } else {
            this.__loadMainPage();
          }
        }, this.__loadLoginPage, this);
      }
    },

    __loadLoginPage: function() {
      this.__disconnectWebSocket();
      const view = new osparc.auth.LoginPage();
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
      this.__loadView(new osparc.desktop.MainPage(studyId), {
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
      osparc.auth.Manager.getInstance().logout();
      this.__restart();
    },

    __connectWebSocket: function() {
      // open web socket
      osparc.wrapper.WebSocket.getInstance().connect();
    },

    __disconnectWebSocket: function() {
      // open web socket
      osparc.wrapper.WebSocket.getInstance().disconnect();
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
    },

    __loadCommonCss: function() {
      const commonCssUri = qx.util.ResourceManager.getInstance().toUri("common/common.css");
      qx.module.Css.includeStylesheet(commonCssUri);
    }
  }
});
