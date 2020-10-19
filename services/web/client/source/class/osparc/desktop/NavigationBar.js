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
    BUTTON_OPTIONS: {
      font: "title-14",
      allowGrowY: false,
      minWidth: 32,
      minHeight: 32
    },

    PAGE_CONTEXT: {
      0: "dashboard",
      1: "workbench",
      2: "slideshow"
    },

    areSlidesEnabled: function() {
      return new Promise((resolve, reject) => {
        osparc.utils.LibVersions.getPlatformName()
          .then(platformName => {
            if (["dev", "master"].includes(platformName)) {
              resolve(true);
            } else {
              resolve(false);
            }
          });
      });
    }
  },

  members: {
    __dashboardBtn: null,
    __dashboardLabel: null,
    __slideBtns: null,
    __startSlidesBtn: null,
    __stopSlidesBtn: null,
    __studyTitle: null,
    __workbenchNodesLayout: null,
    __guidedNodesLayout: null,

    buildLayout: function() {
      this.getChildControl("logo");

      this._add(new qx.ui.core.Spacer(20));

      this.__dashboardBtn = this.getChildControl("dashboard-button");
      this.__dashboardLabel = this.getChildControl("dashboard-label");

      this._add(new qx.ui.core.Spacer(20));

      this.__slideBtns = this.getChildControl("slideshow-buttons").set({
        visibility: "excluded"
      });

      this._add(new qx.ui.core.Spacer(20));

      const studyTitle = this.__studyTitle = this.getChildControl("study-title");
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

      this.__workbenchNodesLayout = this.getChildControl("workbench-nodes-path-container");
      this.__guidedNodesLayout = this.getChildControl("guided-nodes-path-container");

      this._add(new qx.ui.core.Spacer(), {
        flex: 1
      });

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
        case "slideshow-buttons":
          control = this.__createSlideBtns();
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
        case "workbench-nodes-path-container":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
            alignY: "middle"
          }));
          this._add(control);
          break;
        case "guided-nodes-path-container":
          control = new qx.ui.toolbar.Part().set({
            alignY: "middle"
          });
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

    __createNodePathBtn: function(nodeId) {
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const btn = new qx.ui.form.Button().set(this.self().BUTTON_OPTIONS);
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
      return btn;
    },

    __createNodeSlideBtn: function(nodeId, pos) {
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const btn = new qx.ui.toolbar.RadioButton().set(this.self().BUTTON_OPTIONS);
      const node = study.getWorkbench().getNode(nodeId);
      if (node) {
        node.bind("label", btn, "label", {
          converter: val => (pos+1).toString() + " - " + val
        });
      }
      btn.addListener("execute", function() {
        this.fireDataEvent("nodeSelected", nodeId);
      }, this);
      return btn;
    },

    __setPathButtons: function(nodeIds) {
      if (this.getPageContext() === "workbench") {
        this.__setWorkbenchBtnsVis(true);
        this.__setSlidesBtnsVis(false);

        if (nodeIds.length > 1) {
          this.__studyTitle.exclude();
          this.__workbenchNodesLayout.show();
        } else {
          this.__studyTitle.show();
          this.__workbenchNodesLayout.exclude();
        }
      } else {
        this.__setWorkbenchBtnsVis(false);
        this.__setSlidesBtnsVis(true);
      }
    },

    __populateWorkbenchNodesLayout: function() {
      const study = this.getStudy();
      const nodeIds = study.getWorkbench().getPathIds(study.getUi().getCurrentNodeId());
      this.__setPathButtons(nodeIds);

      this.__workbenchNodesLayout.removeAll();
      for (let i=0; i<nodeIds.length; i++) {
        const nodeId = nodeIds[i];
        const btn = this.__createNodePathBtn(nodeId);
        this.__workbenchNodesLayout.add(btn);

        if (i<nodeIds.length-1) {
          const arrow = new qx.ui.basic.Label(">").set({
            font: "text-14"
          });
          this.__workbenchNodesLayout.add(arrow);
        }
        if (i === nodeIds.length-1) {
          btn.setFont("title-14");
        }
      }
    },

    __populateGuidedNodesLayout: function() {
      const study = this.getStudy();
      if (study) {
        this.__guidedNodesLayout.removeAll();
        const radioGroup = new qx.ui.form.RadioGroup();
        const currentNodeId = study.getUi().getCurrentNodeId();
        const slideShow = study.getUi().getSlideshow();
        const nodes = [];
        for (let nodeId in slideShow) {
          const node = slideShow[nodeId];
          nodes.push({
            ...node,
            nodeId
          });
        }
        nodes.sort((a, b) => (a.position > b.position) ? 1 : -1);
        let selectedBtn = null;
        nodes.forEach(node => {
          const btn = this.__createNodeSlideBtn(node.nodeId, node.position);
          if (node.nodeId === currentNodeId) {
            selectedBtn = btn;
          }
          this.__guidedNodesLayout.add(btn);
          radioGroup.add(btn);
        });
        if (selectedBtn) {
          radioGroup.setSelection([selectedBtn]);
        }
        radioGroup.setAllowEmptySelection(false);
      }
    },

    _applyPageContext: function(newCtxt) {
      switch (newCtxt) {
        case "dashboard":
          this.__dashboardLabel.show();
          this.__dashboardBtn.exclude();
          this.__resetSlideBtnsVis(false);
          this.__setWorkbenchBtnsVis(false);
          this.__setSlidesBtnsVis(false);
          break;
        case "workbench":
          this.__dashboardLabel.exclude();
          this.__dashboardBtn.show();
          this.__resetSlideBtnsVis(true);
          this.__setWorkbenchBtnsVis(true);
          this.__setSlidesBtnsVis(false);
          this.__populateWorkbenchNodesLayout();
          break;
        case "slideshow":
          this.__dashboardLabel.exclude();
          this.__dashboardBtn.show();
          this.__resetSlideBtnsVis(true);
          this.__setWorkbenchBtnsVis(false);
          this.__setSlidesBtnsVis(true);
          this.__populateGuidedNodesLayout();
          break;
      }
    },

    __resetSlideBtnsVis: function() {
      this.self().areSlidesEnabled()
        .then(areSlidesEnabled => {
          const context = ["workbench", "slideshow"].includes(this.getPageContext());
          if (areSlidesEnabled && context) {
            const study = this.getStudy();
            if (Object.keys(study.getUi().getSlideshow()).length) {
              this.__slideBtns.show();
              if (this.getPageContext() === "slideshow") {
                this.__startSlidesBtn.exclude();
                this.__stopSlidesBtn.show();
              } else if (this.getPageContext() === "workbench") {
                this.__startSlidesBtn.show();
                this.__stopSlidesBtn.exclude();
              }
              return;
            }
          }
          this.__slideBtns.exclude();
        });
    },

    __setWorkbenchBtnsVis: function(show) {
      if (show) {
        this.__studyTitle.show();
        this.__workbenchNodesLayout.show();
      } else {
        this.__studyTitle.exclude();
        this.__workbenchNodesLayout.exclude();
      }
    },

    __setSlidesBtnsVis: function(show) {
      if (show) {
        this.__guidedNodesLayout.show();
      } else {
        this.__guidedNodesLayout.exclude();
      }
    },

    __createSlideBtns: function() {
      const menu = new qx.ui.toolbar.Part();

      const startBtn = this.__startSlidesBtn = new qx.ui.toolbar.Button(this.tr("Start slides"));
      startBtn.addListener("execute", () => {
        this.fireEvent("slidesStart");
      }, this);
      menu.add(startBtn);

      const stopBtn = this.__stopSlidesBtn = new qx.ui.toolbar.Button(this.tr("Stop slides"));
      stopBtn.addListener("execute", () => {
        this.fireEvent("slidesStop");
      }, this);
      menu.add(stopBtn);

      return menu;
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
        study.bind("name", this.__studyTitle, "value");
        study.getUi().addListener("changeSlideshow", () => {
          this.__resetSlideBtnsVis();
        });
        study.getUi().addListener("changeCurrentNodeId", () => {
          if (this.getPageContext() === "workbench") {
            this.__populateWorkbenchNodesLayout();
          } else if (this.getPageContext() === "slideshow") {
            this.__populateGuidedNodesLayout();
          }
        });
      }
    }
  }
});
