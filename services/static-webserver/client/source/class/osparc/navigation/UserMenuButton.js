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
      const preferencesWindow = new osparc.desktop.preferences.PreferencesWindow();
      preferencesWindow.center();
      preferencesWindow.open();
    }
  },

  members: {
    __serverStatics: null,

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
        case "clusters":
          control = new qx.ui.menu.Button(this.tr("Clusters"));
          control.exclude();
          osparc.utils.DisabledPlugins.isClustersDisabled()
            .then(isDisabled => {
              if (isDisabled === false) {
                control.show();
              }
            });
          control.addListener("execute", () => osparc.utils.Clusters.popUpClustersDetails(), this);
          this.getMenu().add(control);
          break;
        case "quick-start":
          control = new qx.ui.menu.Button(this.tr("Quick Start"));
          control.addListener("execute", () => {
            const tutorialWindow = new osparc.component.tutorial.Slides();
            tutorialWindow.center();
            tutorialWindow.open();
          });
          this.getMenu().add(control);
          break;
        case "license":
          control = new qx.ui.menu.Button(this.tr("License"));
          osparc.navigation.Manuals.getLicenseURL()
            .then(licenseURL => control.addListener("execute", () => window.open(licenseURL)));
          this.getMenu().add(control);
          break;
        case "about":
          control = new qx.ui.menu.Button(this.tr("About"));
          control.addListener("execute", () => osparc.About.getInstance().open());
          osparc.utils.Utils.setIdToWidget(control, "userMenuAboutBtn");
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

    populateSimpleMenu: function() {
      this.getChildControl("preferences");
      this.getChildControl("clusters");
      if (osparc.utils.Utils.isProduct("tis")) {
        this.getMenu().addSeparator();
        this.getChildControl("quick-start");
      }
      this.getMenu().addSeparator();
      this.getChildControl("license");
      this.getChildControl("about");
      this.getMenu().addSeparator();
      this.getChildControl("logout");
    },

    populateExtendedMenu: function() {
      osparc.data.Resources.get("statics")
        .then(statics => {
          this.__serverStatics = statics;
          this.getChildControl("theme-switcher");
          this.getChildControl("preferences");
          this.getChildControl("clusters");
          this.getMenu().addSeparator();
          this.__addManualsToMenu();
          this.__addFeedbacksToMenu();
          if (osparc.utils.Utils.isProduct("tis")) {
            this.getChildControl("quick-start");
          }
          this.getMenu().addSeparator();
          this.getChildControl("license");
          this.getChildControl("about");
          this.getMenu().addSeparator();
          this.getChildControl("logout");
        });
    },

    __addManualsToMenu: function() {
      const menu = this.getMenu();
      osparc.navigation.Manuals.addManualButtonsToMenu(menu);
    },

    __addFeedbacksToMenu: function() {
      const menu = this.getMenu();
      osparc.navigation.Manuals.addSupportButtonsToMenu(menu);
    }
  }
});
