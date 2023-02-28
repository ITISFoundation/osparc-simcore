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

    const userEmail = osparc.auth.Data.getInstance().getEmail() || "bizzy@itis.ethz.ch";
    const menu = new qx.ui.menu.Menu().set({
      font: "text-14"
    });
    this.set({
      font: "text-14",
      icon: osparc.utils.Avatar.getUrl(userEmail, 32),
      label: "bizzy",
      menu
    });
    osparc.auth.Data.getInstance().bind("firstName", this, "label");
    osparc.utils.Utils.setIdToWidget(this, "userMenuMainBtn");

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
      activityWindow.add(new osparc.component.service.manager.ActivityManager());
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
        case "preferences":
          control = new qx.ui.menu.Button(this.tr("Preferences"));
          control.addListener("execute", () => osparc.navigation.UserMenuButton.openPreferences(), this);
          osparc.utils.Utils.setIdToWidget(control, "userMenuPreferencesBtn");
          this.getMenu().add(control);
          break;
        case "organizations":
          control = new qx.ui.menu.Button(this.tr("Organizations"));
          osparc.desktop.preferences.PreferencesWindow.evaluateOrganizationsButton(control);
          control.addListener("execute", () => {
            const preferences = osparc.navigation.UserMenuButton.openPreferences();
            preferences.openOrganizations();
          }, this);
          this.getMenu().add(control);
          break;
        case "clusters":
          control = new qx.ui.menu.Button(this.tr("Clusters"));
          control.exclude();
          if (osparc.product.Utils.showClusters()) {
            osparc.utils.DisabledPlugins.isClustersDisabled()
              .then(isDisabled => {
                if (isDisabled === false) {
                  control.show();
                }
              });
          }
          control.addListener("execute", () => osparc.utils.Clusters.popUpClustersDetails(), this);
          this.getMenu().add(control);
          break;
        case "quick-start": {
          control = new qx.ui.menu.Button(this.tr("Quick Start"));
          const tutorial = osparc.product.tutorial.Utils.getTutorial();
          if (tutorial) {
            control.addListener("execute", () => {
              const tutorialWindow = tutorial.tutorial();
              tutorialWindow.center();
              tutorialWindow.open();
            });
            this.getMenu().add(control);
          }
          break;
        }
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
        case "about-product":
          control = new qx.ui.menu.Button(this.tr("About Product"));
          osparc.store.StaticInfo.getInstance().getDisplayName()
            .then(displayName => {
              control.getChildControl("label").setRich(true);
              control.setLabel(this.tr("About ") + displayName);
            });
          control.addListener("execute", () => osparc.product.AboutProduct.getInstance().open());
          this.getMenu().add(control);
          break;
        case "logout":
          control = new qx.ui.menu.Button(this.tr("Logout"));
          control.addListener("execute", () => qx.core.Init.getApplication().logout());
          osparc.utils.Utils.setIdToWidget(control, "userMenuLogoutBtn");
          this.getMenu().add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    populateMenu: function() {
      this.getMenu().removeAll();
      this.getChildControl("preferences");
      this.getChildControl("organizations");
      this.getChildControl("clusters");
      if (osparc.product.tutorial.Utils.getTutorial()) {
        this.getMenu().addSeparator();
        this.getChildControl("quick-start");
      }
      this.getMenu().addSeparator();
      this.getChildControl("about");
      if (osparc.product.Utils.showAboutProduct()) {
        this.getChildControl("about-product");
      }
      this.getChildControl("license");
      this.getMenu().addSeparator();
      this.getChildControl("logout");
    },

    populateMenuCompact: function() {
      this.getMenu().removeAll();
      osparc.data.Resources.get("statics")
        .then(() => {
          this.getChildControl("preferences");
          this.getChildControl("organizations");
          this.getChildControl("clusters");
          this.getMenu().addSeparator();

          // this part gets injected
          this.__addManualsToMenu(); // already contains the Quick Start
          this.__addFeedbacksToMenu();
          this.getChildControl("theme-switcher");

          this.getMenu().addSeparator();
          this.getChildControl("about");
          if (!osparc.product.Utils.isProduct("osparc")) {
            this.getChildControl("about-product");
          }
          this.getChildControl("license");
          this.getMenu().addSeparator();
          this.getChildControl("logout");
        });
    },

    __addManualsToMenu: function() {
      const menu = this.getMenu();
      osparc.store.Support.addManualButtonsToMenu(menu);
    },

    __addFeedbacksToMenu: function() {
      const menu = this.getMenu();
      osparc.store.Support.addSupportButtonsToMenu(menu);
    }
  }
});
