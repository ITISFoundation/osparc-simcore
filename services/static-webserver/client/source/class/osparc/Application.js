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

  statics: {
    MIN_WIDTH: 1240,
    MIN_HEIGHT: 700
  },

  members: {
    __current: null,
    __themeSwitcher: null,
    __mainPage: null,

    /**
     * This method contains the initial application code and gets called
     * during startup of the application
     */
    main: function() {
      // Call super class
      this.base();

      // Load user preferred theme if present
      const themeName = osparc.utils.Utils.localCache.getTheme();
      if (themeName && themeName !== qx.theme.manager.Meta.getInstance().getTheme().name) {
        const preferredTheme = qx.Theme.getByName(themeName);
        const themes = qx.Theme.getAll();
        if (preferredTheme && Object.keys(themes).includes(preferredTheme.name)) {
          qx.theme.manager.Meta.getInstance().setTheme(preferredTheme);
        }
      }

      this.__preventAutofillBrowserSyles();

      // Enable logging in debug variant
      if (qx.core.Environment.get("qx.debug")) {
        // support native logging capabilities, e.g. Firebug for Firefox
        qx.log.appender.Native;
      }

      const webSocket = osparc.wrapper.WebSocket.getInstance();
      webSocket.addListener("connect", () => osparc.io.WatchDog.getInstance().setOnline(true));
      webSocket.addListener("disconnect", () => osparc.io.WatchDog.getInstance().setOnline(false));
      webSocket.addListener("logout", () => this.logout());
      // alert the users that they are about to navigate away
      // from osparc. unfortunately it is not possible
      // to provide our own message here
      window.addEventListener("beforeunload", e => {
        if (webSocket.isConnected()) {
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
      osparc.auth.Manager.getInstance().addListener("logout", () => this.__restart(), this);

      this.__initRouting();
      this.__loadCommonCss();

      this.__updateTabName();
      this.__updateFavicon();
      this.__checkCookiesAccepted();

      // onload, load, DOMContentLoaded, appear... didn't work
      // bit of a hack
      setTimeout(() => this.__checkScreenSize(), 100);
      window.addEventListener("resize", () => this.__checkScreenSize());
    },

    __checkScreenSize: function() {
      osparc.utils.LibVersions.getPlatformName()
        .then(platformName => {
          const preferencesSettings = osparc.desktop.preferences.Preferences.getInstance();
          if (platformName !== "master" && preferencesSettings.getConfirmWindowSize()) {
            const title = this.tr("Oops, the window is a bit too small!");
            const tooSmallWindow = new osparc.ui.window.SingletonWindow("tooSmallScreen", title).set({
              height: 100,
              width: 400,
              layout: new qx.ui.layout.VBox(),
              appearance: "service-window",
              showMinimize: false,
              showMaximize: false,
              showClose: false,
              resizable: false,
              modal: true,
              contentPadding: 10
            });
            const w = document.documentElement.clientWidth;
            const h = document.documentElement.clientHeight;
            if (this.self().MIN_WIDTH > w || this.self().MIN_HEIGHT > h) {
              const product = this.tr("This app");
              const baseTextMsg = this.tr(`
                 is designed for slightly bigger window size.<br>\
                A mininum window size of ${this.self().MIN_WIDTH}x${this.self().MIN_HEIGHT} is recommended<br>\
                Touch devices are not fully supported.
              `);
              const label = new qx.ui.basic.Label().set({
                value: product+ baseTextMsg,
                rich: true
              });
              const displayNameKey = osparc.store.StaticInfo.getInstance().getDisplayNameKey();
              osparc.store.StaticInfo.getInstance().getValue(displayNameKey)
                .then(displayName => {
                  label.setValue(displayName + baseTextMsg);
                });
              tooSmallWindow.add(label, {
                flex: 1
              });
              const okBtn = new qx.ui.form.Button(this.tr("Got it")).set({
                allowGrowX: false,
                allowGrowY: false,
                alignX: "right"
              });
              okBtn.addListener("execute", () => tooSmallWindow.close());
              tooSmallWindow.add(okBtn);
              setTimeout(() => tooSmallWindow.center(), 100);
              tooSmallWindow.center();
              tooSmallWindow.open();
            } else {
              tooSmallWindow.close();
            }
          }
        });
    },

    __initRouting: function() {
      const urlFragment = osparc.utils.Utils.parseURLFragment();
      if (urlFragment.nav && urlFragment.nav.length) {
        this.__rerouteNav(urlFragment);
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

    __rerouteNav: function(urlFragment) {
      const page = urlFragment.nav[0];
      switch (page) {
        case "study": {
          // Route: /#/study/{id}
          if (urlFragment.nav.length > 1) {
            osparc.utils.Utils.cookie.deleteCookie("user");
            osparc.auth.Manager.getInstance().validateToken()
              .then(() => {
                const studyId = urlFragment.nav[1];
                this.__loadMainPage(studyId);
              })
              .catch(() => this.__loadLoginPage());
          }
          break;
        }
        case "view": {
          // Route: /#/view/?project_id={studyId}&viewer_node_id={viewerNodeId}
          if (urlFragment.params && urlFragment.params.project_id && urlFragment.params.viewer_node_id) {
            osparc.utils.Utils.cookie.deleteCookie("user");
            const studyId = urlFragment.params.project_id;
            const viewerNodeId = urlFragment.params.viewer_node_id;

            osparc.auth.Manager.getInstance().validateToken()
              .then(data => {
                if (["anonymous", "guest"].includes(data.role.toLowerCase())) {
                  this.__loadNodeViewerPage(studyId, viewerNodeId);
                } else {
                  this.__loadMainPage(studyId);
                }
              });
          }
          break;
        }
        case "registration": {
          // Route: /#/registration/?invitation={token}
          if (urlFragment.params && urlFragment.params.invitation) {
            osparc.utils.Utils.cookie.deleteCookie("user");
            this.__restart();
          }
          break;
        }
        case "reset-password": {
          // Route: /#/reset-password/?code={resetCode}
          if (urlFragment.params && urlFragment.params.code) {
            osparc.utils.Utils.cookie.deleteCookie("user");
            this.__restart();
          }
          break;
        }
        case "error": {
          // Route: /#/error/?message={errorMessage}&status_code={statusCode}
          if (urlFragment.params && urlFragment.params.message) {
            let msg = urlFragment.params.message;
            // Relpace plus sign in URL query string by spaces
            msg = msg.replace(/\+/g, "%20");
            msg = decodeURIComponent(msg);
            osparc.utils.Utils.cookie.deleteCookie("user");
            const errorPage = new osparc.Error().set({
              code: urlFragment.params.status_code,
              messages: [
                msg
              ]
            });
            this.__loadView(errorPage);
          }
          break;
        }
        case "form-sandbox": {
          this.__loadView(new osparc.desktop.FormSandboxPage(), {}, false);
        }
      }
    },

    __updateTabName: function() {
      osparc.utils.LibVersions.getPlatformName()
        .then(platformName => {
          if (osparc.utils.Utils.isInZ43()) {
            document.title += " Z43";
          }
          if (platformName) {
            document.title += ` (${platformName})`;
          }
        });
    },

    __updateFavicon: function() {
      let link = document.querySelector("link[rel~='icon']");
      if (!link) {
        link = document.createElement("link");
        link.rel = "icon";
        document.getElementsByTagName("head")[0].appendChild(link);
      }
      link.href = "/resource/osparc/favicon-"+qx.core.Environment.get("product.name")+".png";
    },

    __checkCookiesAccepted: function() {
      osparc.utils.LibVersions.getPlatformName()
        .then(platformName => {
          if (platformName !== "master") {
            if (!osparc.CookiePolicy.areCookiesAccepted()) {
              const cookiePolicy = new osparc.CookiePolicy();
              const title = this.tr("Cookie Policy");
              // "tis" and "s4llite" include the license agreement
              const height = (osparc.utils.Utils.isProduct("tis") || osparc.utils.Utils.isProduct("s4llite")) ? 180 : 145;
              const win = osparc.ui.window.Window.popUpInWindow(cookiePolicy, title, 400, height).set({
                clickAwayClose: false,
                resizable: false,
                showClose: false
              });
              cookiePolicy.addListener("cookiesAccepted", () => {
                osparc.CookiePolicy.acceptCookies();
                win.close();
              }, this);
              cookiePolicy.addListener("cookiesDeclined", () => {
                osparc.CookiePolicy.declineCookies();
                win.close();
              }, this);
            }
          }
        });
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
        osparc.auth.Manager.getInstance().validateToken()
          .then(data => {
            if (data.role.toLowerCase() === "guest") {
              // Logout a guest trying to access the Dashboard
              osparc.auth.Manager.getInstance().logout();
            } else {
              this.__loadMainPage();
            }
          })
          .catch(() => this.__loadLoginPage());
      }
    },

    __loadLoginPage: function() {
      this.__disconnectWebSocket();
      let view = null;
      switch (qx.core.Environment.get("product.name")) {
        case "s4l":
        case "s4llite":
          view = new osparc.auth.LoginPageS4L();
          this.__loadView(view);
          break;
        case "tis":
          view = new osparc.auth.LoginPageTI();
          this.__loadView(view);
          break;
        default: {
          view = new osparc.auth.LoginPage();
          this.__loadView(view, {
            top: "15%"
          });
          break;
        }
      }
      view.addListener("done", () => this.__restart(), this);
    },

    __loadMainPage: function(studyId = null) {
      // Invalidate the entire cache
      osparc.store.Store.getInstance().invalidate();

      osparc.data.Resources.getOne("profile")
        .then(profile => {
          if ("expirationDate" in profile) {
            const now = new Date();
            const today = new Date(now.toISOString().slice(0, 10));
            const expirationDay = new Date(profile["expirationDate"]);
            const daysToExpiration = osparc.utils.Utils.daysBetween(today, expirationDay);
            if (daysToExpiration < 7) {
              osparc.utils.Utils.expirationMessage(daysToExpiration)
                .then(msg => osparc.component.message.FlashMessenger.getInstance().logAs(msg, "WARNING"));
            }
          }
          if (studyId) {
            osparc.store.Store.getInstance().setCurrentStudyId(studyId);
          }
          this.__connectWebSocket();
          const mainPage = this.__mainPage = new osparc.desktop.MainPage();
          this.__loadView(mainPage);
        });
    },

    __loadNodeViewerPage: function(studyId, viewerNodeId) {
      // Invalidate the entire cache
      osparc.store.Store.getInstance().invalidate();

      this.__connectWebSocket();
      this.__loadView(new osparc.viewer.MainPage(studyId, viewerNodeId));
    },

    __loadView: function(view, opts, clearUrl=true) {
      const options = {
        top: 0,
        bottom: 0,
        left: 0,
        right: 0,
        ...opts
      };
      this.assert(view!==null);
      // Update root document and currentness
      let doc = this.getRoot();
      if (doc.hasChildren()) {
        if (this.__current) {
          doc.remove(this.__current);
        }
        if (this.__themeSwitcher) {
          doc.remove(this.__themeSwitcher);
          this.__themeSwitcher = null;
        }
      }
      doc.add(view, options);
      this.__current = view;
      if (!(view instanceof osparc.desktop.MainPage)) {
        this.__themeSwitcher = new osparc.ui.switch.ThemeSwitcherFormBtn().set({
          backgroundColor: "transparent"
        });
        doc.add(this.__themeSwitcher, {
          top: 10,
          right: 15
        });
      }

      // Clear URL
      if (clearUrl) {
        window.history.replaceState(null, "", "/");
      }
    },

    /**
     * Resets session and restarts
    */
    logout: function() {
      osparc.data.PollTasks.getInstance().removeTasks();
      osparc.auth.Manager.getInstance().logout();
      if (this.__mainPage) {
        this.__mainPage.closeEditor();
      }
      osparc.utils.Utils.closeHangingWindows();
      osparc.store.Store.getInstance().dispose();
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
