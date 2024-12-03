/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.navigation.UserMenu", {
  extend: qx.ui.menu.Menu,

  construct: function() {
    this.base(arguments);

    this.set({
      font: "text-14"
    });
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "mini-profile-view":
          control = new osparc.navigation.MiniProfileMenuButton();
          this.setMinWidth(150);
          this.addAt(control, 0);
          break;
        case "theme-switcher":
          control = new osparc.ui.switch.ThemeSwitcherMenuBtn();
          osparc.utils.Utils.setIdToWidget(control, "userMenuThemeSwitcherBtn");
          this.add(control);
          break;
        case "log-in":
          control = new qx.ui.menu.Button(this.tr("Log in"));
          control.addListener("execute", () => window.open(window.location.href, "_blank"));
          this.add(control);
          break;
        case "user-center":
          control = new qx.ui.menu.Button(this.tr("My Account"));
          osparc.utils.Utils.setIdToWidget(control, "userMenuMyAccountBtn");
          control.addListener("execute", () => osparc.desktop.account.MyAccountWindow.openWindow(), this);
          this.add(control);
          break;
        case "admin-center":
          control = new qx.ui.menu.Button(this.tr("Admin Center"));
          control.addListener("execute", () => osparc.admin.AdminCenterWindow.openWindow(), this);
          this.add(control);
          break;
        case "po-center":
          control = new qx.ui.menu.Button(this.tr("PO Center"));
          control.addListener("execute", () => osparc.po.POCenterWindow.openWindow(), this);
          this.add(control);
          break;
        case "tester-center":
          control = new qx.ui.menu.Button(this.tr("Tester Center"));
          control.addListener("execute", () => osparc.tester.TesterCenterWindow.openWindow(), this);
          this.add(control);
          break;
        case "billing-center":
          control = new qx.ui.menu.Button(this.tr("Billing Center"));
          osparc.utils.Utils.setIdToWidget(control, "userMenuBillingCenterBtn");
          control.addListener("execute", () => {
            const walletsEnabled = osparc.desktop.credits.Utils.areWalletsEnabled();
            if (walletsEnabled) {
              osparc.desktop.credits.BillingCenterWindow.openWindow();
            }
          }, this);
          this.add(control);
          break;
        case "preferences":
          control = new qx.ui.menu.Button(this.tr("Preferences"));
          control.addListener("execute", () => osparc.navigation.UserMenuButton.openPreferences(), this);
          osparc.utils.Utils.setIdToWidget(control, "userMenuPreferencesBtn");
          this.add(control);
          break;
        case "organizations":
          control = new qx.ui.menu.Button(this.tr("Organizations")).set({
            visibility: osparc.data.Permissions.getInstance().canDo("user.organizations.create") ? "visible" :"excluded"
          });
          osparc.utils.Utils.setIdToWidget(control, "userMenuOrganizationsBtn");
          control.addListener("execute", () => osparc.desktop.organizations.OrganizationsWindow.openWindow(), this);
          this.add(control);
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
          this.add(control);
          break;
        case "market":
          control = new qx.ui.menu.Button(this.tr("Market"));
          control.addListener("execute", () => osparc.vipMarket.MarketWindow.openWindow());
          this.add(control);
          break;
        case "about":
          control = new qx.ui.menu.Button(this.tr("About oSPARC"));
          osparc.utils.Utils.setIdToWidget(control, "userMenuAboutBtn");
          control.addListener("execute", () => osparc.About.getInstance().open());
          this.add(control);
          break;
        case "about-product": {
          control = new qx.ui.menu.Button(this.tr("About Product"));
          osparc.utils.Utils.setIdToWidget(control, "userMenuAboutProductBtn");
          const displayName = osparc.store.StaticInfo.getInstance().getDisplayName();
          control.getChildControl("label").setRich(true);
          control.setLabel(this.tr("About ") + displayName);
          control.addListener("execute", () => osparc.product.AboutProduct.getInstance().open());
          this.add(control);
          break;
        }
        case "license":
          control = new qx.ui.menu.Button(this.tr("License"));
          osparc.utils.Utils.setIdToWidget(control, "userMenuLicenseBtn");
          osparc.store.Support.getLicenseURL()
            .then(licenseURL => control.addListener("execute", () => window.open(licenseURL)));
          this.add(control);
          break;
        case "tip-lite-button":
          control = new qx.ui.menu.Button(this.tr("Access Full TIP"));
          osparc.utils.Utils.setIdToWidget(control, "userMenuAccessTIPBtn");
          control.addListener("execute", () => osparc.product.TIPTeaser.getInstance().open());
          this.add(control);
          break;
        case "log-out": {
          const authData = osparc.auth.Data.getInstance();
          control = new qx.ui.menu.Button(authData.isGuest() ? this.tr("Exit") : this.tr("Log out"));
          control.addListener("execute", () => {
            this.exclude();
            qx.core.Init.getApplication().logout();
          });
          osparc.utils.Utils.setIdToWidget(control, "userMenuLogoutBtn");
          this.add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    populateMenu: function() {
      this.removeAll();

      this.getChildControl("mini-profile-view");

      if (osparc.auth.Data.getInstance().isGuest()) {
        this.getChildControl("log-in");
      } else {
        this.getChildControl("user-center");
        if (osparc.data.Permissions.getInstance().isAdmin()) {
          this.getChildControl("admin-center");
        }
        if (osparc.data.Permissions.getInstance().isProductOwner()) {
          this.getChildControl("po-center");
        }
        if (osparc.data.Permissions.getInstance().isTester()) {
          this.getChildControl("tester-center");
        }
        if (osparc.desktop.credits.Utils.areWalletsEnabled()) {
          this.getChildControl("billing-center");
        }
        this.getChildControl("preferences");
        this.getChildControl("organizations");
        this.getChildControl("clusters");
      }
      this.addSeparator();

      this.getChildControl("theme-switcher");
      this.addSeparator();

      this.__addAnnouncements();

      if (osparc.product.Utils.showS4LStore()) {
        this.getChildControl("market");
      }

      this.getChildControl("about");
      if (osparc.product.Utils.showAboutProduct()) {
        this.getChildControl("about-product");
      }
      this.getChildControl("license");
      if (osparc.product.Utils.isProduct("tiplite")) {
        this.getChildControl("tip-lite-button");
      }
      this.addSeparator();

      this.getChildControl("log-out");

      osparc.utils.Utils.prettifyMenu(this);
    },

    __addAnnouncements: function() {
      const announcementUIFactory = osparc.announcement.AnnouncementUIFactory.getInstance();
      if (announcementUIFactory.hasUserMenuAnnouncement()) {
        announcementUIFactory.createUserMenuAnnouncements().forEach(announcement => this.add(announcement));
      }
    },

    populateMenuCompact: function() {
      this.removeAll();
      const authData = osparc.auth.Data.getInstance();
      if (authData.isGuest()) {
        this.getChildControl("log-in");
      } else {
        this.getChildControl("user-center");
        if (osparc.data.Permissions.getInstance().isAdmin()) {
          this.getChildControl("admin-center");
        }
        if (osparc.data.Permissions.getInstance().isProductOwner()) {
          this.getChildControl("po-center");
        }
        if (osparc.data.Permissions.getInstance().isTester()) {
          this.getChildControl("tester-center");
        }
        if (osparc.desktop.credits.Utils.areWalletsEnabled()) {
          this.getChildControl("billing-center");
        }
        this.getChildControl("preferences");
        this.getChildControl("organizations");
        this.getChildControl("clusters");
      }
      this.addSeparator();

      // quick starts
      osparc.store.Support.addQuickStartToMenu(this);
      osparc.store.Support.addGuidedToursToMenu(this);

      // manuals
      osparc.store.Support.addManualButtonsToMenu(this);
      this.addSeparator();

      // feedbacks
      osparc.store.Support.addSupportButtonsToMenu(this);
      this.addSeparator();

      this.getChildControl("theme-switcher");
      this.addSeparator();

      this.__addAnnouncements();
      
      if (osparc.product.Utils.showS4LStore()) {
        this.getChildControl("market");
      }

      this.getChildControl("about");
      if (!osparc.product.Utils.isProduct("osparc")) {
        this.getChildControl("about-product");
      }
      this.getChildControl("license");
      if (osparc.product.Utils.isProduct("tiplite")) {
        this.getChildControl("tip-lite-button");
      }
      this.addSeparator();
      this.getChildControl("log-out");

      osparc.utils.Utils.prettifyMenu(this);
    }
  }
});
