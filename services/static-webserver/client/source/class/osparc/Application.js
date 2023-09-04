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

  members: {
    __current: null,
    __themeSwitcher: null,
    __mainPage: null,
    __openViewAfterLogin: null,

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

      const intlTelInput = osparc.wrapper.IntlTelInput.getInstance();
      intlTelInput.init();

      const threejs = osparc.wrapper.Three.getInstance();
      threejs.init();

      const announcementsTracker = osparc.AnnouncementsTracker.getInstance();
      announcementsTracker.startTracker();

      const webSocket = osparc.wrapper.WebSocket.getInstance();
      webSocket.addListener("connect", () => osparc.io.WatchDog.getInstance().setOnline(true));
      webSocket.addListener("disconnect", () => osparc.io.WatchDog.getInstance().setOnline(false));
      webSocket.addListener("logout", () => this.logout());
      // alert the users that they are about to navigate away
      // from osparc. unfortunately it is not possible
      // to provide our own message here
      window.addEventListener("beforeunload", e => {
        const downloadLinkTracker = osparc.DownloadLinkTracker.getInstance();
        // The downloadLinkTracker uses an external link for downloading files.
        // When it starts (click), triggers an unload event. This condition avoids the false positive
        if (!downloadLinkTracker.isDownloading() && webSocket.isConnected()) {
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

      this.__startupChecks();
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
      this.__openViewAfterLogin = null;
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
              .catch(() => {
                osparc.store.VendorInfo.getInstance().getVendor()
                  .then(vendor => {
                    const landingPage = "has_landing_page" in vendor ? vendor["has_landing_page"] : false;
                    this.__loadLoginPage(landingPage);
                  })
                  .catch(() => this.__loadLoginPage(false));
              });
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
        case "wallets": {
          // Route: /#/wallets
          this.__openViewAfterLogin = "wallets";
          osparc.utils.Utils.cookie.deleteCookie("user");
          osparc.auth.Manager.getInstance().validateToken()
            .then(() => this.__loadMainPage())
            .catch(() => {
              osparc.store.VendorInfo.getInstance().getVendor()
                .then(vendor => {
                  const landingPage = "has_landing_page" in vendor ? vendor["has_landing_page"] : false;
                  this.__loadLoginPage(landingPage);
                })
                .catch(() => this.__loadLoginPage(false));
            });
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
            this.__loadView(errorPage, {
              top: "10%"
            });
          }
          break;
        }
        case "form-sandbox": {
          this.__loadView(new osparc.desktop.FormSandboxPage(), {}, false);
        }
      }
    },

    __updateTabName: function() {
      osparc.store.StaticInfo.getInstance().getPlatformName()
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

    __startupChecks: function() {
      osparc.store.StaticInfo.getInstance().getPlatformName()
        .then(platformName => {
          if (platformName !== "master") {
            // first, pop up new relaese window
            this.__checkNewRelease();
            // then, pop up cookies accepted window. It will go on top.
            this.__checkCookiesAccepted();
          }
        });
    },

    __checkNewRelease: function() {
      const lastCommit = osparc.utils.Utils.localCache.getLastCommitVcsRefUI();
      const thisCommit = osparc.utils.LibVersions.getVcsRef();
      if (lastCommit) {
        if (lastCommit !== thisCommit) {
          const newRelease = new osparc.NewRelease();
          const title = this.tr("New Release");
          const win = osparc.ui.window.Window.popUpInWindow(newRelease, title, 350, 170).set({
            clickAwayClose: false,
            resizable: false,
            showClose: true
          });
          const closeBtn = win.getChildControl("close-button");
          osparc.utils.Utils.setIdToWidget(closeBtn, "newReleaseCloseBtn");
        }
      } else {
        osparc.utils.Utils.localCache.setLastCommitVcsRefUI(thisCommit);
      }
    },

    __checkCookiesAccepted: function() {
      if (!osparc.CookiePolicy.areCookiesAccepted()) {
        const cookiePolicy = new osparc.CookiePolicy();
        let title = this.tr("Privacy Policy");
        let height = 160;
        if (osparc.product.Utils.showLicenseExtra()) {
          // "tis" and "s4llite" include the license terms
          title = this.tr("Privacy Policy and License Terms");
          height = 210;
        }
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
          .catch(() => {
            osparc.store.VendorInfo.getInstance().getVendor()
              .then(vendor => {
                const landingPage = "has_landing_page" in vendor ? vendor["has_landing_page"] : false;
                this.__loadLoginPage(landingPage);
              })
              .catch(() => this.__loadLoginPage(false));
          });
      }
    },

    __loadLoginPage: function(landingPage = false) {
      this.__disconnectWebSocket();
      let view = null;
      switch (qx.core.Environment.get("product.name")) {
        case "s4l":
        case "s4llite":
          if (landingPage) {
            view = new osparc.product.landingPage.s4llite.Page();
            view.addListener("loginPressed", () => {
              view.close();
              this.__loadLoginPage(false);
            });
          } else {
            view = new osparc.auth.LoginPageS4L();
          }
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
      // logged in

      // Invalidate the entire cache
      osparc.store.Store.getInstance().invalidate();

      osparc.data.Resources.get("permissions");

      osparc.data.Resources.getOne("profile")
        .then(profile => {
          this.__connectWebSocket();

          if (osparc.auth.Data.getInstance().isGuest()) {
            osparc.utils.Utils.createAccountMessage()
              .then(msg => osparc.component.message.FlashMessenger.getInstance().logAs(msg, "WARNING"));
          } else if ("expirationDate" in profile) {
            const now = new Date();
            const today = new Date(now.toISOString().slice(0, 10));
            const expirationDay = new Date(profile["expirationDate"]);
            const daysToExpiration = osparc.utils.Utils.daysBetween(today, expirationDay);
            if (daysToExpiration < 7) {
              osparc.utils.Utils.expirationMessage(daysToExpiration)
                .then(msg => osparc.component.message.FlashMessenger.getInstance().logAs(msg, "WARNING"));
            }
          }

          if ("preferences" in profile) {
            const bePreferences = profile["preferences"];
            const fePreferences = qx.util.PropertyUtil.getProperties(osparc.Preferences);
            const preferencesSettings = osparc.Preferences.getInstance();
            Object.entries(bePreferences).forEach(([key, data]) => {
              const value = data.value;
              if (fePreferences.includes(key)) {
                preferencesSettings.set(key, value);
              } else {
                switch (key) {
                  case "dontShowAnnouncements":
                    break;
                  case "services":
                    break;
                  case "themeName":
                    if (value) {
                      preferencesSettings.setThemeName(value);
                    }
                    break;
                  case "preferredWalletId":
                    if (value) {
                      preferencesSettings.setPreferredWalletId(value);
                    }
                    break;
                }
              }
            });
          }

          if (studyId) {
            osparc.store.Store.getInstance().setCurrentStudyId(studyId);
          }

          const mainPage = this.__mainPage = new osparc.desktop.MainPage(this.__openViewAfterLogin);
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
      if (!(view instanceof osparc.desktop.MainPage || view instanceof osparc.product.landingPage.s4llite.Page)) {
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
      osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("You are logged out"));

      osparc.data.PollTasks.getInstance().removeTasks();
      osparc.MaintenanceTracker.getInstance().stopTracker();
      osparc.AnnouncementsTracker.getInstance().stopTracker();
      osparc.auth.Manager.getInstance().logout();
      if (this.__mainPage) {
        this.__mainPage.closeEditor();
      }
      osparc.panddy.Panddy.getInstance().stop();
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
