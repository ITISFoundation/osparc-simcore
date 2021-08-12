/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget containing:
 * - LogoOnOff
 * - Dashboard (button)
 * - List of buttons for node navigation (only study editing)
 * - User menu
 *   - Preferences
 *   - Help
 *   - About
 *   - Logout
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let navBar = new osparc.navigation.NavigationBar();
 *   this.getRoot().add(navBar);
 * </pre>
 */

qx.Class.define("osparc.navigation.NavigationBar", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(10).set({
      alignY: "middle"
    }));

    osparc.data.Resources.get("statics")
      .then(statics => {
        this.__serverStatics = statics;
        this.buildLayout();
      });

    this.set({
      paddingLeft: 10,
      paddingRight: 10,
      height: this.self().HEIGHT,
      maxHeight: this.self().HEIGHT,
      backgroundColor: "background-main-lighter"
    });
  },

  events: {
    "dashboardPressed": "qx.event.type.Event",
    "slidesStart": "qx.event.type.Event",
    "slidesStop": "qx.event.type.Event"
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      nullable: true,
      apply: "_applyStudy"
    },

    pageContext: {
      check: ["dashboard", "workbench", "slideshow"],
      nullable: false,
      apply: "_applyPageContext"
    }
  },

  statics: {
    HEIGHT: 50,

    BUTTON_OPTIONS: {
      font: "text-14",
      allowGrowY: false,
      minWidth: 32,
      minHeight: 32
    },

    PAGE_CONTEXT: {
      0: "dashboard",
      1: "workbench",
      2: "slideshow"
    }
  },

  members: {
    __serverStatics: null,

    buildLayout: function() {
      this.getChildControl("logo");

      this._add(new qx.ui.core.Spacer(20));

      this.getChildControl("dashboard-button");
      this.getChildControl("dashboard-label");

      this._add(new qx.ui.core.Spacer(20));

      this.getChildControl("slideshow-start").set({
        visibility: "excluded"
      });
      this.getChildControl("slideshow-stop").set({
        visibility: "excluded"
      });

      this._add(new qx.ui.core.Spacer(20));

      this.getChildControl("read-only-icon");

      const studyTitle = this.getChildControl("study-title");
      studyTitle.addListener("editValue", evt => {
        if (evt.getData() !== studyTitle.getValue()) {
          studyTitle.setFetching(true);
          const params = {
            name: evt.getData()
          };
          this.getStudy().updateStudy(params)
            .then(() => {
              studyTitle.setFetching(false);
            })
            .catch(err => {
              studyTitle.setFetching(false);
              console.error(err);
              osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an error while updating the title."), "ERROR");
            });
        }
      }, this);

      this._add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      this.getChildControl("tasks-button");
      this.getChildControl("manual");
      this.getChildControl("feedback");
      this.getChildControl("theme-switch");
      this.getChildControl("user-menu");

      this.setPageContext("dashboard");
    },

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "logo": {
          control = osparc.component.widget.LogoOnOff.getInstance();
          this._add(control);
          break;
        }
        case "dashboard-button":
          control = new osparc.ui.form.FetchButton(this.tr("Dashboard"), "@FontAwesome5Solid/arrow-left/16").set({
            ...this.self().BUTTON_OPTIONS,
            font: "title-14"
          });
          osparc.utils.Utils.setIdToWidget(control, "dashboardBtn");
          control.addListener("execute", () => {
            this.fireEvent("dashboardPressed");
          }, this);
          this._add(control);
          break;
        case "dashboard-label":
          control = new qx.ui.basic.Label(this.tr("Dashboard")).set({
            font: "text-16"
          });
          this._add(control);
          break;
        case "read-only-icon":
          control = new qx.ui.basic.Image("@FontAwesome5Solid/eye/22").set({
            visibility: "excluded",
            paddingRight: 10,
            toolTipText: "Read Only"
          });
          this._add(control);
          break;
        case "slideshow-start":
          control = this.__createSlideStartBtn();
          this._add(control);
          break;
        case "slideshow-stop":
          control = this.__createSlideStopBtn();
          this._add(control);
          break;
        case "study-title":
          control = new osparc.ui.form.EditLabel().set({
            visibility: "excluded",
            labelFont: "title-14",
            inputFont: "text-14",
            editable: osparc.data.Permissions.getInstance().canDo("study.update")
          });
          this._add(control);
          break;
        case "tasks-button": {
          control = new osparc.component.task.TasksButton();
          this._add(control);
          break;
        }
        case "manual":
          control = this.__createManualMenuBtn();
          control.set(this.self().BUTTON_OPTIONS);
          this._add(control);
          break;
        case "feedback":
          control = this.__createFeedbackMenuBtn();
          control.set(this.self().BUTTON_OPTIONS);
          this._add(control);
          break;
        case "theme-switch":
          control = new osparc.ui.switch.ThemeSwitcher();
          this._add(control);
          break;
        case "user-menu":
          control = this.__createUserMenuBtn();
          control.set(this.self().BUTTON_OPTIONS);
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    _applyPageContext: function(newCtxt) {
      switch (newCtxt) {
        case "dashboard":
          this.getChildControl("dashboard-label").show();
          this.getChildControl("dashboard-button").exclude();
          this.getChildControl("read-only-icon").exclude();
          this.__resetSlidesBtnsVis(false);
          this.getChildControl("study-title").exclude();
          break;
        case "workbench":
        case "slideshow":
          this.getChildControl("dashboard-label").exclude();
          this.getChildControl("dashboard-button").show();
          this.__resetSlidesBtnsVis(true);
          this.getChildControl("study-title").show();
          break;
      }
    },

    __resetSlidesBtnsVis: function() {
      const areSlidesEnabled = osparc.data.Permissions.getInstance().canDo("study.slides");
      const context = ["workbench", "slideshow"].includes(this.getPageContext());
      if (areSlidesEnabled && context) {
        const study = this.getStudy();
        if (study && Object.keys(study.getUi().getSlideshow()).length) {
          if (this.getPageContext() === "slideshow") {
            this.getChildControl("slideshow-start").exclude();
            this.getChildControl("slideshow-stop").show();
          } else if (this.getPageContext() === "workbench") {
            this.getChildControl("slideshow-start").show();
            this.getChildControl("slideshow-stop").exclude();
          }
          return;
        }
      }
      this.getChildControl("slideshow-start").exclude();
      this.getChildControl("slideshow-stop").exclude();
    },

    __createSlideStartBtn: function() {
      const startBtn = new qx.ui.form.Button(this.tr("Guided Mode"), "@FontAwesome5Solid/caret-square-right/16").set({
        ...this.self().BUTTON_OPTIONS
      });
      startBtn.addListener("execute", () => {
        this.fireEvent("slidesStart");
      }, this);
      return startBtn;
    },

    __createSlideStopBtn: function() {
      const stopBtn = new qx.ui.form.Button(this.tr("Guided Mode"), "@FontAwesome5Solid/stop/16").set({
        ...this.self().BUTTON_OPTIONS
      });
      stopBtn.addListener("execute", () => {
        this.fireEvent("slidesStop");
      }, this);
      return stopBtn;
    },

    __createManualMenuBtn: function() {
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

      let control = new qx.ui.core.Widget();
      if (manuals.length === 1) {
        const manual = manuals[0];
        control = new osparc.ui.form.LinkButton(null, manual.icon, manual.url).set({
          toolTipText: manual.label
        });
      } else if (manuals.length > 1) {
        const menu = new qx.ui.menu.Menu().set({
          font: "text-14"
        });

        manuals.forEach(manual => {
          const manualBtn = new qx.ui.menu.Button(manual.label);
          manualBtn.addListener("execute", () => {
            window.open(manual.url);
          }, this);
          menu.add(manualBtn);
        });

        control = new qx.ui.form.MenuButton(null, "@FontAwesome5Solid/book/22", menu).set({
          toolTipText: this.tr("Manuals")
        });
      }
      return control;
    },

    __createFeedbackMenuBtn: function() {
      const menu = new qx.ui.menu.Menu().set({
        font: "text-14"
      });

      const newGHIssueBtn = new qx.ui.menu.Button(this.tr("Issue in GitHub"));
      newGHIssueBtn.addListener("execute", this.__openGithubIssueInfoDialog, this);
      menu.add(newGHIssueBtn);

      if (osparc.utils.Utils.isInZ43()) {
        const newFogbugzIssueBtn = new qx.ui.menu.Button(this.tr("Issue in Fogbugz"));
        newFogbugzIssueBtn.addListener("execute", this.__openFogbugzIssueInfoDialog, this);
        menu.add(newFogbugzIssueBtn);
      }

      const feedbackAnonBtn = new qx.ui.menu.Button(this.tr("Anonymous feedback"));
      feedbackAnonBtn.addListener("execute", () => {
        if (this.__serverStatics.feedbackFormUrl) {
          window.open(this.__serverStatics.feedbackFormUrl);
        }
      });
      menu.add(feedbackAnonBtn);

      const feedbackBtn = new qx.ui.form.MenuButton(null, "@FontAwesome5Solid/comments/22", menu).set({
        toolTipText: this.tr("Give us feedback")
      });
      return feedbackBtn;
    },

    __createUserMenuBtn: function() {
      const menu = new qx.ui.menu.Menu().set({
        font: "text-14"
      });

      const activityManager = new qx.ui.menu.Button(this.tr("Activity manager"));
      activityManager.addListener("execute", this.__openActivityManager, this);
      menu.add(activityManager);

      const preferences = new qx.ui.menu.Button(this.tr("Preferences"));
      preferences.addListener("execute", this.__onOpenAccountSettings, this);
      osparc.utils.Utils.setIdToWidget(preferences, "userMenuPreferencesBtn");
      menu.add(preferences);

      menu.addSeparator();

      const aboutBtn = new qx.ui.menu.Button(this.tr("About"));
      aboutBtn.addListener("execute", () => osparc.About.getInstance().open());
      osparc.utils.Utils.setIdToWidget(aboutBtn, "userMenuAboutBtn");
      menu.add(aboutBtn);

      menu.addSeparator();

      const logout = new qx.ui.menu.Button(this.tr("Logout"));
      logout.addListener("execute", e => {
        qx.core.Init.getApplication().logout();
      });
      osparc.utils.Utils.setIdToWidget(logout, "userMenuLogoutBtn");
      menu.add(logout);

      const userEmail = osparc.auth.Data.getInstance().getEmail() || "bizzy@itis.ethz.ch";
      const userName = osparc.auth.Data.getInstance().getUserName() || "bizzy";
      const userBtn = new qx.ui.form.MenuButton(null, null, menu);
      userBtn.getChildControl("icon").getContentElement()
        .setStyles({
          "border-radius": "16px"
        });
      userBtn.set({
        icon: osparc.utils.Avatar.getUrl(userEmail, 32),
        label: userName
      });
      osparc.utils.Utils.setIdToWidget(userBtn, "userMenuMainBtn");

      return userBtn;
    },

    __onOpenAccountSettings: function() {
      const preferencesWindow = new osparc.desktop.preferences.PreferencesWindow();
      preferencesWindow.center();
      preferencesWindow.open();
    },

    __openActivityManager: function() {
      const activityWindow = new osparc.ui.window.SingletonWindow("activityManager", this.tr("Activity manager")).set({
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

    __openGithubIssueInfoDialog: function() {
      const issueConfirmationWindow = new osparc.ui.window.Dialog("Information", null,
        this.tr("To create an issue in GitHub, you must have an account in GitHub and be already logged-in.")
      );
      const contBtn = new qx.ui.toolbar.Button(this.tr("Continue"), "@FontAwesome5Solid/external-link-alt/12");
      contBtn.addListener("execute", () => {
        window.open(osparc.utils.issue.Github.getNewIssueUrl());
        issueConfirmationWindow.close();
      }, this);
      const loginBtn = new qx.ui.toolbar.Button(this.tr("Log in in GitHub"), "@FontAwesome5Solid/external-link-alt/12");
      loginBtn.addListener("execute", () => window.open("https://github.com/login"), this);
      issueConfirmationWindow.addButton(contBtn);
      issueConfirmationWindow.addButton(loginBtn);
      issueConfirmationWindow.addCancelButton();
      issueConfirmationWindow.open();
    },

    __openFogbugzIssueInfoDialog: function() {
      const issueConfirmationWindow = new osparc.ui.window.Dialog("Information", null,
        this.tr("To create an issue in Fogbugz, you must have an account in Fogbugz and be already logged-in.")
      );
      const contBtn = new qx.ui.toolbar.Button(this.tr("Continue"), "@FontAwesome5Solid/external-link-alt/12");
      contBtn.addListener("execute", () => {
        const statics = this.__serverStatics;
        if (statics) {
          const fbNewIssueUrl = osparc.utils.issue.Fogbugz.getNewIssueUrl(statics);
          if (fbNewIssueUrl) {
            window.open(fbNewIssueUrl);
            issueConfirmationWindow.close();
          }
        }
      }, this);
      const loginBtn = new qx.ui.toolbar.Button(this.tr("Log in in Fogbugz"), "@FontAwesome5Solid/external-link-alt/12");
      loginBtn.addListener("execute", () => {
        const statics = this.__serverStatics;
        if (statics && statics.fogbugzLoginUrl) {
          window.open(statics.fogbugzLoginUrl);
        }
      }, this);
      issueConfirmationWindow.addButton(contBtn);
      issueConfirmationWindow.addButton(loginBtn);
      issueConfirmationWindow.addCancelButton();
      issueConfirmationWindow.open();
    },

    _applyStudy: function(study) {
      if (study) {
        study.bind("name", this.getChildControl("study-title"), "value");
        study.bind("readOnly", this.getChildControl("read-only-icon"), "visibility", {
          converter: value => value ? "visible" : "excluded"
        });
        study.getUi().addListener("changeSlideshow", () => {
          this.__resetSlidesBtnsVis();
        });
      }
    }
  }
});
