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
 * @asset(common/*)
 */

qx.Class.define("osparc.Application", {
  extend: qx.application.Standalone,
  include: [
    qx.locale.MTranslation
  ],

  members: {
    __current: null,
    __mainPage: null,

    /**
     * This method contains the initial application code and gets called
     * during startup of the application
     */
    main: async function() {
      // Call super class
      this.base();

      // Enable logging in debug variant
      if (qx.core.Environment.get("qx.debug")) {
        // support native logging capabilities, e.g. Firebug for Firefox
        qx.log.appender.Native;
      }

      await this.__preloadCalls();

      this.__preventAutofillBrowserStyles();
      this.__loadCommonCss();
      this.__updateTabName();
      if (osparc.utils.Utils.isDevelopmentPlatform()) {
        this.__updateMetaTags();
        this.__setDeviceSpecificIcons();
      }
      if (qx.core.Environment.get("product.name") === "s4lengine") {
        const view = new osparc.auth.BlurredLoginPageS4LEngineering();
        this.__loadView(view);
        return;
      }

      // libs
      osparc.wrapper.IntlTelInput.getInstance().init();
      osparc.wrapper.Three.getInstance().init();

      // trackers
      osparc.announcement.Tracker.getInstance().startTracker();
      osparc.WindowSizeTracker.getInstance().startTracker();
      osparc.ConsoleErrorTracker.getInstance().startTracker();

      const webSocket = osparc.wrapper.WebSocket.getInstance();
      webSocket.addListener("connect", () => osparc.WatchDog.getInstance().setOnline(true));
      webSocket.addListener("disconnect", () => osparc.WatchDog.getInstance().setOnline(false));
      webSocket.addListener("logout", () => this.logout(qx.locale.Manager.tr("You were logged out")));
      // alert the users that they are about to navigate away
      // from osparc. unfortunately it is not possible
      // to provide our own message here
      window.addEventListener("beforeunload", e => {
        const downloadLinkTracker = osparc.DownloadLinkTracker.getInstance();
        if (
          // The downloadLinkTracker uses an external link for downloading files.
          // When it starts (click), triggers an unload event. This condition avoids the false positive
          !downloadLinkTracker.isDownloading() &&
          // allow reloading in login page
          webSocket.isConnected() &&
          // allow reloading in dashboard
          osparc.store.Store.getInstance().getCurrentStudy()
        ) {
          // Cancel the event as stated by the standard.
          e.preventDefault();
          // Chrome requires returnValue to be set.
          e.returnValue = "";
        }
      });

      // Setting up auth manager
      osparc.auth.Manager.getInstance().addListener("loggedOut", () => this.__closeAllAndToLoginPage(), this);

      this.__initRouting();
      this.__startupChecks();
    },

    __preloadCalls: async function() {
      await osparc.store.Store.getInstance().preloadCalls();
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
        case "request-account": {
          // Route: /#/request-account
          osparc.utils.Utils.cookie.deleteCookie("user");
          this.__restart();
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
            // Replace plus sign in URL query string by spaces
            msg = msg.replace(/\+/g, "%20");
            msg = decodeURIComponent(msg);
            osparc.utils.Utils.cookie.deleteCookie("user");
            const errorPage = new osparc.ErrorPage().set({
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
      const platformName = osparc.store.StaticInfo.getInstance().getPlatformName();
      if (osparc.utils.Utils.isInZ43()) {
        document.title += " Z43";
      }
      if (platformName) {
        document.title += ` (${platformName})`;
      }
    },



    __setDeviceSpecificIcons: function() {
      const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
      const isAndroid = /android/i.test(navigator.userAgent);
      // default icons
      this.__updateMetaTags();
      this.__setDefaultIcons()
      if (isIOS) {
        this.__setIOSpIcons();
      } else if (isAndroid) {
        this.__setGoogleIcons();
      }
    },

    __getProductMetaData: function() {
      let productName = osparc.product.Utils.getProductName();
      if (osparc.product.Utils.isS4LProduct() || osparc.product.Utils.isProduct("s4llite")) {
        productName = "s4l";
      } else if (osparc.product.Utils.isProduct("tis") || osparc.product.Utils.isProduct("tiplite")) {
        productName = "tis";
      }

      const productColor = qx.theme.manager.Color.getInstance().resolve("product-color");
      return {
        productName: productName,
        productColor: productColor,
      }
    },

    __updateMetaTags: function() {
      // check device type and only set the icons for the device type
      // i.e iOS, Android or windows etc
      const themeColorMeta = document.querySelector("meta[name='theme-color']");
      const tileColorMeta = document.querySelector("meta[name='msapplication-TileColor']");
      const tileImageMeta = document.querySelector("meta[name='msapplication-TileImage']");
      const maskIconMeta = document.querySelector("meta[rel='mask-icon']");
      const shortIconMeta = document.querySelector("link[rel='icon']");
      const manifestLink = document.querySelector("link[rel='manifest']");
      const msApplicationLink = document.querySelector("link[rel='msapplication-config']");

      const {productName, productColor} = this.__getProductMetaData();

      if (themeColorMeta) {
        themeColorMeta.setAttribute("content", productColor);
      }

      if (tileColorMeta && tileImageMeta) {
        const maskIcon = `../resource/osparc/${productName}/icons/ms-icon-150x150.png`
        tileColorMeta.setAttribute("content", productColor);
        tileImageMeta.setAttribute("content", maskIcon);
      }

      if (shortIconMeta) {
        const maskIconPath = `../resource/osparc/${productName}/icons/favicon-96x96.png`
        shortIconMeta.setAttribute("href", maskIconPath);
      }

      if (maskIconMeta) {
        const maskIconPath = `../resource/osparc/${productName}/apple-icon-fallback.png`
        maskIconMeta.setAttribute("href", maskIconPath);
      }

      if (manifestLink) {
        const manifestPath = `../resource/osparc/${productName}/manifest.json`
        manifestLink.setAttribute("href", manifestPath);
      }

      if (msApplicationLink) {
        const msApplicationPath = `../resource/osparc/${productName}/broswserconfig.xml`
        msApplicationLink.setAttribute("href", msApplicationPath);
      }
    },

    __setDefaultIcons: function() {
      const {productName} = this.__getProductMetaData()
      const resourcePath = `../resource/osparc/${productName}/icons/`;
      const favIconUrls = [
        "favicon-16x16.png",
        "favicon-32x32.png",
        "favicon-96x96.png"
      ];

      const iconSizes = [
        "16x16", "32x32", "96x96"
      ];
      favIconUrls.forEach((url, index) => {
        let link = document.createElement("link");
        link.setAttribute("rel", "icon");
        link.setAttribute("sizes", iconSizes[index]);
        link.setAttribute("type", "image/png");
        link.setAttribute("href", resourcePath + url);
        document.head.appendChild(link);
      });
    },

    __setGoogleIcons: function() {
      const {productName} = this.__getProductMetaData()
      const resourcePath = `../resource/osparc/${productName}/icons`;

      const favIconUrls = [
        "android-icon-48x48.png",
        "android-icon-192x192.png",
      ];

      const iconSizes = [
        "48x48", "192x192"
      ];
      favIconUrls.forEach((url, index) => {
        let link = document.createElement("link");
        link.setAttribute("rel", "icon");
        link.setAttribute("sizes", iconSizes[index]);
        link.setAttribute("type", "image/png");
        link.setAttribute("href", resourcePath + url);
        document.head.appendChild(link);
      });
    },

    __setIOSpIcons: function() {
      // Array of promises to resolve icon URLs for Apple Touch Icons
      const {productName} = this.__getProductMetaData()
      const resourcePath = `../resource/osparc/${productName}/icons`;

      const appleIconUrls = [
        "apple-icon-57x57.png",
        "apple-icon-60x60.png",
        "apple-icon-72x72.png",
        "apple-icon-76x76.png",
        "apple-icon-114x114.png",
        "apple-icon-120x120.png",
        "apple-icon-144x144.png",
        "apple-icon-152x152.png",
        "apple-icon-180x180.png"
      ];

      const appleIconSizes = [
        "57x57", "60x60", "72x72", "76x76", "114x114", "120x120", "144x144", "152x152", "180x180"
      ];
      appleIconUrls.forEach((url, index) => {
        let link = document.createElement("link");
        link.setAttribute("rel", "apple-touch-icon");
        link.setAttribute("sizes", appleIconSizes[index]);
        link.setAttribute("href", resourcePath + url);
        document.head.appendChild(link);
      });
    },

    __startupChecks: function() {
      // first, pop up new release window
      this.__checkNewRelease();

      const platformName = osparc.store.StaticInfo.getInstance().getPlatformName();
      if (platformName !== "master") {
        // then, pop up cookies accepted window. It will go on top.
        this.__checkCookiesAccepted();
      }
    },

    __checkNewRelease: function() {
      if (osparc.NewRelease.firstTimeISeeThisFrontend()) {
        const newRelease = new osparc.NewRelease();
        const title = this.tr("New Release");
        const win = osparc.ui.window.Window.popUpInWindow(newRelease, title, 350, 135).set({
          clickAwayClose: false,
          resizable: false,
          showClose: true
        });
        const closeBtn = win.getChildControl("close-button");
        osparc.utils.Utils.setIdToWidget(closeBtn, "newReleaseCloseBtn");
      }
    },

    __checkCookiesAccepted: function() {
      if (!osparc.CookiePolicy.areCookiesAccepted()) {
        const cookiePolicy = new osparc.CookiePolicy();
        let title = this.tr("Privacy Policy");
        let height = 160;
        if (osparc.product.Utils.showLicenseExtra()) {
          // "tis", "tiplite" and "s4llite" include the license terms
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
      if (isLogged) {
        this.__loadMainPage();
      } else {
        osparc.auth.Manager.getInstance().validateToken()
          .then(data => {
            if (data.role.toLowerCase() === "guest") {
              // Logout a guest trying to access the Dashboard
              this.logout();
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
        case "s4lacad":
        case "s4ldesktop":
        case "s4ldesktopacad":
          view = new osparc.auth.LoginPageS4L();
          break;
        case "tis":
        case "tiplite":
          view = new osparc.auth.LoginPageTI();
          break;
        default: {
          view = new osparc.auth.LoginPageOsparc();
          break;
        }
      }
      this.__loadView(view);
      view.addListener("done", () => this.__restart(), this);
    },

    __loadMainPage: function(studyId = null) {
      // logged in
      osparc.WindowSizeTracker.getInstance().evaluateTooSmallDialog();
      osparc.data.Resources.getOne("profile")
        .then(profile => {
          if (profile) {
            this.__connectWebSocket();

            if (osparc.auth.Data.getInstance().isGuest()) {
              const msg = osparc.utils.Utils.createAccountMessage();
              osparc.FlashMessenger.getInstance().logAs(msg, "WARNING");
            } else if ("expirationDate" in profile) {
              const now = new Date();
              const today = new Date(now.toISOString().slice(0, 10));
              const expirationDay = new Date(profile["expirationDate"]);
              const daysToExpiration = osparc.utils.Utils.daysBetween(today, expirationDay);
              if (daysToExpiration < 7) {
                const msg = osparc.utils.Utils.expirationMessage(daysToExpiration);
                osparc.FlashMessenger.getInstance().logAs(msg, "WARNING");
              }
            }

            if ("preferences" in profile) {
              const bePreferences = profile["preferences"];
              const fePreferences = Object.keys(qx.util.PropertyUtil.getProperties(osparc.Preferences));
              const preferencesSettings = osparc.Preferences.getInstance();
              Object.entries(bePreferences).forEach(([key, data]) => {
                const value = data.value;
                switch (key) {
                  case "themeName":
                    if (value) {
                      preferencesSettings.setThemeName(value);
                    }
                    break;
                  case "preferredWalletId":
                    if (value) {
                      preferencesSettings.setPreferredWalletId(parseInt(value));
                    }
                    break;
                  default:
                    if (fePreferences.includes(key)) {
                      preferencesSettings.set(key, value);
                    }
                }
              });
            }

            if (studyId) {
              osparc.store.Store.getInstance().setCurrentStudyId(studyId);
            }

            let mainPage = null;
            if (osparc.product.Utils.getProductName().includes("s4ldesktop")) {
              mainPage = new osparc.desktop.MainPageDesktop();
            } else {
              mainPage = new osparc.desktop.MainPage();
            }
            this.__mainPage = mainPage;
            this.__loadView(mainPage);
          }
        })
        .catch(err => console.error(err));
    },

    __loadNodeViewerPage: async function(studyId, viewerNodeId) {
      this.__connectWebSocket();
      const mainPage = new osparc.viewer.MainPage(studyId, viewerNodeId);
      this.__mainPage = mainPage;
      this.__loadView(mainPage);
    },

    __loadView: function(view, opts, clearUrl=true) {
      const options = {
        top: 0,
        bottom: 0,
        left: 0,
        right: 0,
        ...opts
      };

      // Update root document and currentness
      let doc = this.getRoot();
      if (doc.hasChildren()) {
        if (this.__current) {
          doc.remove(this.__current);
        }
      }
      doc.add(view, options);
      this.__current = view;

      // Clear URL
      if (clearUrl) {
        window.history.replaceState(null, "", "/");
      }
    },

    /**
     * Resets session and restarts
    */
    logout: function(forcedReason) {
      const isLoggedIn = osparc.auth.Manager.getInstance().isLoggedIn();
      if (isLoggedIn) {
        osparc.auth.Manager.getInstance().logout()
          .finally(() => this.__loggedOut(forcedReason));
      } else {
        this.__loggedOut(forcedReason);
      }
    },

    __loggedOut: function(forcedReason) {
      if (forcedReason) {
        osparc.FlashMessenger.getInstance().logAs(forcedReason, "WARNING", 0);
      } else {
        osparc.FlashMessenger.getInstance().logAs(this.tr("You are logged out"), "INFO");
      }
      this.__closeAllAndToLoginPage();
    },

    __closeAllAndToLoginPage: function() {
      osparc.data.PollTasks.getInstance().removeTasks();
      osparc.MaintenanceTracker.getInstance().stopTracker();
      osparc.CookieExpirationTracker.getInstance().stopTracker();
      osparc.NewUITracker.getInstance().stopTracker();
      osparc.announcement.Tracker.getInstance().stopTracker();
      if ("closeEditor" in this.__mainPage) {
        this.__mainPage.closeEditor();
      }
      osparc.utils.Utils.closeHangingWindows();

      // Remove all bindings and Invalidate the entire cache
      const store = osparc.store.Store.getInstance();
      store.removeAllBindings();
      store.invalidateEntireCache();

      // back to the dark theme to make pretty forms
      const validThemes = osparc.ui.switch.ThemeSwitcher.getValidThemes();
      const themeFound = validThemes.find(theme => theme.basename === "ThemeDark");
      if (themeFound) {
        qx.theme.manager.Meta.getInstance().setTheme(themeFound);
      }

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

    __preventAutofillBrowserStyles: function() {
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
