/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.navigation.UserMenuButton", {
  extend: qx.ui.form.MenuButton,

  construct: function() {
    this.base(arguments);

    const authData = osparc.auth.Data.getInstance();

    const userEmail = authData.getEmail() || "bizzy@itis.ethz.ch";
    const menu = new qx.ui.menu.Menu().set({
      font: "text-14"
    });
    osparc.utils.Utils.setIdToWidget(menu, "userMenuMenu");
    this.set({
      font: "text-14",
      icon: osparc.utils.Avatar.getUrl(userEmail, 32),
      label: "bizzy",
      menu
    });
    authData.bind("firstName", this, "label");
    authData.bind("role", this, "label", {
      converter: role => {
        if (role === "anonymous") {
          return "Anonymous";
        }
        if (role === "guest") {
          return "Guest";
        }
        return authData.getFirstName();
      }
    });
    osparc.utils.Utils.setIdToWidget(this, "userMenuBtn");

    this.getChildControl("icon").getContentElement().setStyles({
      "border-radius": "16px"
    });
  },

  statics: {
    openActivityManager: function() {
      const activityWindow = new osparc.ui.window.SingletonWindow("activityManager", qx.locale.Manager.tr("Activity manager")).set({
        height: 600,
        width: 800,
        layout: new qx.ui.layout.Grow(),
        appearance: "service-window",
        showMinimize: false,
        contentPadding: 0
      });
      activityWindow.add(new osparc.activityManager.ActivityManager());
      activityWindow.center();
      activityWindow.open();
    },

    openPreferences: function() {
      const preferencesWindow = osparc.desktop.preferences.PreferencesWindow.openWindow();
      return preferencesWindow;
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "theme-switcher":
          control = new osparc.ui.switch.ThemeSwitcherMenuBtn();
          this.getMenu().add(control);
          break;
        case "log-in":
          control = new qx.ui.menu.Button(this.tr("Log in"));
          control.addListener("execute", () => window.open(window.location.href, "_blank"));
          this.getMenu().add(control);
          break;
        case "user-center":
          control = new qx.ui.menu.Button(this.tr("User Center"));
          control.addListener("execute", () => {
            const walletsEnabled = osparc.desktop.credits.Utils.areWalletsEnabled();
            const userCenterWindow = osparc.desktop.credits.UserCenterWindow.openWindow();
            if (walletsEnabled) {
              userCenterWindow.openOverview();
            }
          }, this);
          this.getMenu().add(control);
          break;
        case "po-center":
          control = new qx.ui.menu.Button(this.tr("PO Center"));
          control.addListener("execute", () => osparc.po.POCenterWindow.openWindow(), this);
          this.getMenu().add(control);
          break;
        case "preferences":
          control = new qx.ui.menu.Button(this.tr("Preferences"));
          control.addListener("execute", () => osparc.navigation.UserMenuButton.openPreferences(), this);
          osparc.utils.Utils.setIdToWidget(control, "userMenuPreferencesBtn");
          this.getMenu().add(control);
          break;
        case "organizations":
          control = new qx.ui.menu.Button(this.tr("Organizations"));
          osparc.desktop.organizations.OrganizationsWindow.evaluateOrganizationsButton(control);
          control.addListener("execute", () => osparc.desktop.organizations.OrganizationsWindow.openWindow(), this);
          this.getMenu().add(control);
          break;
        case "clusters":
          control = new qx.ui.menu.Button(this.tr("Clusters"));
          control.exclude();
          if (osparc.product.Utils.showClusters()) {
            const isDisabled = osparc.utils.DisabledPlugins.isClustersDisabled();
            if (isDisabled === false) {
              control.show();
            }
          }
          control.addListener("execute", () => osparc.cluster.Utils.popUpClustersDetails(), this);
          this.getMenu().add(control);
          break;
        case "license":
          control = new qx.ui.menu.Button(this.tr("License"));
          osparc.store.Support.getLicenseURL()
            .then(licenseURL => control.addListener("execute", () => window.open(licenseURL)));
          this.getMenu().add(control);
          break;
        case "about":
          control = new qx.ui.menu.Button(this.tr("About oSPARC"));
          control.addListener("execute", () => osparc.About.getInstance().open());
          osparc.utils.Utils.setIdToWidget(control, "userMenuAboutBtn");
          this.getMenu().add(control);
          break;
        case "about-product": {
          control = new qx.ui.menu.Button(this.tr("About Product"));
          const displayName = osparc.store.StaticInfo.getInstance().getDisplayName();
          control.getChildControl("label").setRich(true);
          control.setLabel(this.tr("About ") + displayName);
          control.addListener("execute", () => osparc.product.AboutProduct.getInstance().open());
          this.getMenu().add(control);
          break;
        }
        case "log-out": {
          const authData = osparc.auth.Data.getInstance();
          control = new qx.ui.menu.Button(authData.isGuest() ? this.tr("Exit") : this.tr("Log out"));
          control.addListener("execute", () => qx.core.Init.getApplication().logout());
          osparc.utils.Utils.setIdToWidget(control, "userMenuLogoutBtn");
          this.getMenu().add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    populateMenu: function() {
      this.getMenu().removeAll();
      if (osparc.auth.Data.getInstance().isGuest()) {
        this.getChildControl("log-in");
      } else {
        this.getChildControl("user-center");
        if (osparc.data.Permissions.getInstance().isProductOwner()) {
          this.getChildControl("po-center");
        }
        this.getChildControl("preferences");
        this.getChildControl("organizations");
        this.getChildControl("clusters");
      }
      this.getMenu().addSeparator();
      const announcementUIFactory = osparc.announcement.AnnouncementUIFactory.getInstance();
      if (announcementUIFactory.hasUserMenuAnnouncement()) {
        this.getMenu().add(announcementUIFactory.createUserMenuAnnouncement());
      }
      this.getChildControl("about");
      if (osparc.product.Utils.showAboutProduct()) {
        this.getChildControl("about-product");
      }
      this.getChildControl("license");
      this.getMenu().addSeparator();
      this.getChildControl("log-out");
    },

    populateMenuCompact: function() {
      this.getMenu().removeAll();
      const authData = osparc.auth.Data.getInstance();
      if (authData.isGuest()) {
        this.getChildControl("log-in");
      } else {
        this.getChildControl("user-center");
        if (osparc.data.Permissions.getInstance().isProductOwner()) {
          this.getChildControl("po-center");
        }
        this.getChildControl("preferences");
        this.getChildControl("organizations");
        this.getChildControl("clusters");
      }
      this.getMenu().addSeparator();

      // this part gets injected
      const menu = this.getMenu();

      // quick starts
      osparc.store.Support.addQuickStartToMenu(menu);
      osparc.store.Support.addGuidedToursToMenu(menu);

      // manuals
      osparc.store.Support.addManualButtonsToMenu(menu);
      this.getMenu().addSeparator();

      // feedbacks
      osparc.store.Support.addSupportButtonsToMenu(menu);
      this.getMenu().addSeparator();

      this.getChildControl("theme-switcher");
      this.getMenu().addSeparator();

      const announcementUIFactory = osparc.announcement.AnnouncementUIFactory.getInstance();
      if (announcementUIFactory.hasUserMenuAnnouncement()) {
        this.getMenu().add(announcementUIFactory.createUserMenuAnnouncement());
      }
      this.getChildControl("about");
      if (!osparc.product.Utils.isProduct("osparc")) {
        this.getChildControl("about-product");
      }
      this.getChildControl("license");
      this.getMenu().addSeparator();
      this.getChildControl("log-out");
    }
  }
});
