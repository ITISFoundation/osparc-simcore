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

qx.Class.define("osparc.navigation.CloseStudyAndPreferencesButton", {
  extend: qx.ui.toolbar.SplitButton,

  construct: function() {
    this.base(arguments);

    // this.setIcon("@FontAwesome5Solid/door-open/24");
    this.setIcon("@FontAwesome5Solid/desktop/24");

    this.getChildControl("button").set({
      toolTipText: this.tr("Close Study")
    });

    this.getChildControl("arrow").set({
      toolTipText: this.tr("Preferences")
    });

    this.setMenu(new qx.ui.menu.Menu());
    osparc.data.Resources.get("statics")
      .then(statics => {
        this.__serverStatics = statics;
        this.__populateMenu();
      });
  },

  members: {
    __serverStatics: null,

    __populateMenu: function() {
      const menu = this.getMenu();

      if (osparc.ui.switch.ThemeSwitcher.getValidThemes().length === 2) {
        const themeSwitcher = new osparc.ui.switch.ThemeSwitcherMenuBtn();
        menu.add(themeSwitcher);
      }

      const preferences = new qx.ui.menu.Button(this.tr("Preferences"));
      preferences.addListener("execute", osparc.navigation.NavigationBar.openPreferences, this);
      osparc.utils.Utils.setIdToWidget(preferences, "userMenuPreferencesBtn");
      menu.add(preferences);

      menu.addSeparator();

      this.__addManualsToMenu(menu);
      this.__addFeedbacksToMenu(menu);

      menu.addSeparator();

      const about = new qx.ui.menu.Button(this.tr("About"));
      about.addListener("execute", () => osparc.About.getInstance().open());
      osparc.utils.Utils.setIdToWidget(about, "userMenuAboutBtn");
      menu.add(about);

      const logout = new qx.ui.menu.Button(this.tr("Logout"));
      logout.addListener("execute", () => qx.core.Init.getApplication().logout());
      osparc.utils.Utils.setIdToWidget(logout, "userMenuLogoutBtn");
      menu.add(logout);
    },

    __addManualsToMenu: function(menu) {
      const manuals = [];
      if (this.__serverStatics && this.__serverStatics.manualMainUrl) {
        manuals.push({
          label: this.tr("User Manual"),
          icon: "@FontAwesome5Solid/book/22",
          url: this.__serverStatics.manualMainUrl
        });
      }

      if (osparc.utils.Utils.isInZ43() && this.__serverStatics && this.__serverStatics.manualExtraUrl) {
        manuals.push({
          label: this.tr("Z43 Manual"),
          icon: "@FontAwesome5Solid/book-medical/22",
          url: this.__serverStatics.manualExtraUrl
        });
      }

      manuals.forEach(manual => {
        const manualBtn = new qx.ui.menu.Button(manual.label);
        manualBtn.addListener("execute", () => window.open(manual.url), this);
        menu.add(manualBtn);
      });
    },

    __addFeedbacksToMenu: function(menu) {
      const newGHIssueBtn = new qx.ui.menu.Button(this.tr("Issue in GitHub"));
      newGHIssueBtn.addListener("execute", osparc.navigation.NavigationBar.openGithubIssueInfoDialog, this);
      menu.add(newGHIssueBtn);

      if (osparc.utils.Utils.isInZ43()) {
        const newFogbugzIssueBtn = new qx.ui.menu.Button(this.tr("Issue in Fogbugz"));
        newFogbugzIssueBtn.addListener("execute", osparc.navigation.NavigationBar.openFogbugzIssueInfoDialog, this);
        menu.add(newFogbugzIssueBtn);
      }

      const feedbackAnonBtn = new qx.ui.menu.Button(this.tr("Anonymous feedback"));
      feedbackAnonBtn.addListener("execute", () => {
        if (this.__serverStatics.feedbackFormUrl) {
          window.open(this.__serverStatics.feedbackFormUrl);
        }
      });
      menu.add(feedbackAnonBtn);
    }
  }
});
