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
 *   let navBar = new osparc.desktop.NavigationBar();
 *   this.getRoot().add(navBar);
 * </pre>
 */

qx.Class.define("osparc.desktop.NavigationBar", {
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
      height: 50,
      maxHeight: 50,
      backgroundColor: "background-main-lighter"
    });
  },

  events: {
    "nodeSelected": "qx.event.type.Data",
    "dashboardPressed": "qx.event.type.Event"
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      nullable: true,
      apply: "_applyStudy"
    }
  },

  statics: {
    BUTTON_OPTIONS: {
      font: "title-14",
      allowGrowY: false,
      minWidth: 32,
      minHeight: 32
    }
  },

  members: {
    __dashboardBtn: null,
    __dashboardLabel: null,
    __studyTitle: null,
    __mainViewCaptionLayout: null,

    buildLayout: function() {
      this.getChildControl("logo");

      this._add(new qx.ui.core.Spacer(20));

      this.__dashboardBtn = this.getChildControl("dashboard-button");
      this.__dashboardLabel = this.getChildControl("dashboard-label");
      this.__dashboardContext();

      this._add(new qx.ui.core.Spacer(20));

      const studyTitle = this.__studyTitle = this.__createStudyTitle();
      this._add(studyTitle);
      this.__mainViewCaptionLayout = this.getChildControl("study-path-container");

      this._add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      this.getChildControl("manual");
      this.getChildControl("feedback");
      this.getChildControl("theme-switch");
      this.getChildControl("user-menu");
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
          control = new osparc.ui.form.FetchButton(this.tr("Dashboard"), "@FontAwesome5Solid/arrow-left/14");
          osparc.utils.Utils.setIdToWidget(control, "dashboardBtn");
          control.set(this.self().BUTTON_OPTIONS);
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
        case "study-path-container":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
            alignY: "middle"
          }));
          this._add(control);
          break;
        case "manual":
          control = this.__createManualMenuBtn();
          control.set({
            ...this.self().BUTTON_OPTIONS,
            font: "text-14"
          });
          this._add(control);
          break;
        case "feedback":
          control = this.__createFeedbackMenuBtn();
          control.set({
            ...this.self().BUTTON_OPTIONS,
            font: "text-14"
          });
          this._add(control);
          break;
        case "theme-switch":
          control = new osparc.ui.switch.ThemeSwitcher().set({
            checked: qx.theme.manager.Meta.getInstance().getTheme().name === "osparc.theme.ThemeLight"
          });
          this._add(control);
          break;
        case "user-menu":
          control = this.__createUserMenuBtn();
          control.set({
            ...this.self().BUTTON_OPTIONS,
            font: "text-14"
          });
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    getDashboardButton: function() {
      return this.__dashboardBtn;
    },

    setPathButtons: function(nodeIds) {
      this.__mainViewCaptionLayout.removeAll();
      nodeIds.length === 1 ? this.__studyTitle.show() : this.__studyTitle.exclude();
      if (nodeIds.length === 0) {
        this.__dashboardContext(true);
        return;
      }
      this.__dashboardContext(false);
      if (nodeIds.length === 1) {
        return;
      }

      const study = osparc.store.Store.getInstance().getCurrentStudy();
      for (let i=0; i<nodeIds.length; i++) {
        const btn = new qx.ui.form.Button().set(this.self().BUTTON_OPTIONS);
        const nodeId = nodeIds[i];
        if (nodeId === study.getUuid()) {
          study.bind("name", btn, "label");
        } else {
          const node = study.getWorkbench().getNode(nodeId);
          if (node) {
            node.bind("label", btn, "label");
          }
        }
        btn.addListener("execute", function() {
          this.fireDataEvent("nodeSelected", nodeId);
        }, this);
        this.__mainViewCaptionLayout.add(btn);

        if (i<nodeIds.length-1) {
          const arrow = new qx.ui.basic.Label(">").set({
            font: "text-14"
          });
          this.__mainViewCaptionLayout.add(arrow);
        }
        if (i === nodeIds.length-1) {
          this.__dashboardContext(false);
          btn.setFont("title-14");
        }
      }
    },

    __dashboardContext: function(dashboardContext = true) {
      this.__dashboardLabel.setVisibility(dashboardContext ? "visible" : "excluded");
      this.__dashboardBtn.setVisibility(dashboardContext ? "excluded" : "visible");
    },

    studySaved: function() {
      for (let i=0; i<this.__mainViewCaptionLayout.getChildren().length; i++) {
        let widget = this.__mainViewCaptionLayout.getChildren()[i];
        if (widget instanceof qx.ui.form.Button) {
          const waitFor = 500;
          qx.event.Timer.once(ev => {
            widget.removeState("hovered");
          }, this, waitFor);
          widget.addState("hovered");
          return;
        }
      }
    },

    __createManualMenuBtn: function() {
      const manuals = [];
      if (this.__serverStatics && this.__serverStatics.manualMainUrl) {
        manuals.push([this.tr("User manual"), this.__serverStatics.manualMainUrl]);
      }

      if (osparc.utils.Utils.isInZ43() && this.__serverStatics && this.__serverStatics.manualExtraUrl) {
        manuals.push([this.tr("Z43 manual"), this.__serverStatics.manualExtraUrl]);
      }

      let control = new qx.ui.core.Widget();
      if (manuals.length === 1) {
        const manual = manuals[0];
        control = new osparc.ui.form.LinkButton(manual[0], manual[1]).set({
          appearance: "link-button",
          font: "text-14"
        });
      } else if (manuals.length > 1) {
        const menu = new qx.ui.menu.Menu().set({
          font: "text-14"
        });

        manuals.forEach(manual => {
          const manualBtn = new qx.ui.menu.Button(manual[0]);
          manualBtn.addListener("execute", () => {
            window.open(manual[1]);
          }, this);
          menu.add(manualBtn);
        });

        control = new qx.ui.form.MenuButton(this.tr("Manuals"), null, menu);
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

      const feedbackBtn = new qx.ui.form.MenuButton(this.tr("Give us feedback"), null, menu);
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
      loginBtn.addListener("execute", () => window.open("https://z43.fogbugz.com/login"), this);
      issueConfirmationWindow.addButton(contBtn);
      issueConfirmationWindow.addButton(loginBtn);
      issueConfirmationWindow.addCancelButton();
      issueConfirmationWindow.open();
    },

    _applyStudy: function(study) {
      if (study) {
        study.bind("name", this.__studyTitle, "value");
      }
      this.__studyTitle.show();
    },

    __createStudyTitle: function() {
      const studyTitle = new osparc.ui.form.EditLabel().set({
        visibility: "excluded",
        labelFont: "title-14",
        inputFont: "text-14",
        editable: osparc.data.Permissions.getInstance().canDo("study.update")
      });
      studyTitle.addListener("editValue", evt => {
        if (evt.getData() !== this.__studyTitle.getValue()) {
          this.__studyTitle.setFetching(true);
          const params = {
            name: evt.getData()
          };
          this.getStudy().updateStudy(params)
            .then(() => {
              this.__studyTitle.setFetching(false);
            })
            .catch(err => {
              this.__studyTitle.setFetching(false);
              console.error(err);
              osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an error while updating the title."), "ERROR");
            });
        }
      }, this);
      return studyTitle;
    }
  }
});
