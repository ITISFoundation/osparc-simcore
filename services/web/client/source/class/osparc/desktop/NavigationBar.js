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
 * - Dashboard button
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

    this.set({
      paddingLeft: 10,
      paddingRight: 10,
      maxHeight: 50,
      backgroundColor: "background-main-lighter"
    });

    let logo = osparc.component.widget.LogoOnOff.getInstance();
    const logoContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
      alignY: "middle"
    }));
    logoContainer.add(logo);
    const wrapperContainer = new qx.ui.container.Composite(new qx.ui.layout.Canvas());
    wrapperContainer.add(logoContainer, {
      height: "100%"
    });
    const platformLabel = new qx.ui.basic.Label().set({
      font: "text-9"
    });
    osparc.utils.LibVersions.getPlatformName()
      .then(platformName => platformLabel.setValue(platformName.toUpperCase()));
    wrapperContainer.add(platformLabel, {
      bottom: 3,
      right: 0
    });
    this._add(wrapperContainer);
    this._add(new qx.ui.toolbar.Separator());

    const dashboardBtn = this.__dashboardBtn = this.__getDashboardButton();
    this.__highlightDashboard();
    this._add(dashboardBtn);

    this._add(new qx.ui.toolbar.Separator());

    this.__studyTitle = this.__createStudyTitle();
    this._add(this.__studyTitle);

    let hBox = new qx.ui.layout.HBox(5).set({
      alignY: "middle"
    });
    let mainViewCaptionLayout = this.__mainViewCaptionLayout = new qx.ui.container.Composite(hBox);
    this._add(mainViewCaptionLayout);

    this._add(new qx.ui.core.Spacer(5), {
      flex: 1
    });

    this._add(new osparc.ui.form.LinkButton(this.tr("User manual"), "https://docs.osparc.io").set({
      appearance: "link-button",
      font: "text-14"
    }));

    this._add(new osparc.ui.form.LinkButton(this.tr("Give us feedback"), this.self().FEEDBACK_FORM_URL).set({
      appearance: "link-button",
      font: "text-14"
    }));

    const userEmail = osparc.auth.Data.getInstance().getEmail() || "bizzy@itis.ethz.ch";
    const userName = osparc.auth.Data.getInstance().getUserName() || "bizzy";

    const userBtn = this.__createUserBtn();
    userBtn.set({
      ...this.self().BUTTON_OPTIONS,
      icon: osparc.utils.Avatar.getUrl(userEmail, 32),
      label: userName
    });

    this._add(userBtn);
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
    FEEDBACK_FORM_URL: "https://docs.google.com/forms/d/e/1FAIpQLSe232bTigsM2zV97Kjp2OhCenl6o9gNGcDFt2kO_dfkIjtQAQ/viewform?usp=sf_link",
    BUTTON_OPTIONS: {
      font: "title-14",
      allowGrowY: false,
      minWidth: 32,
      minHeight: 32
    }
  },

  members: {
    __dashboardBtn: null,
    __mainViewCaptionLayout: null,

    __getDashboardButton: function() {
      const dashboardBtn = new qx.ui.form.Button(this.tr("Dashboard"));
      osparc.utils.Utils.setIdToWidget(dashboardBtn, "dashboardBtn");
      dashboardBtn.set(this.self().BUTTON_OPTIONS);
      dashboardBtn.addListener("execute", () => {
        this.fireEvent("dashboardPressed");
      }, this);
      return dashboardBtn;
    },

    __getDashboardLabel: function() {
      const dashboardLabel = new qx.ui.basic.Label(this.tr("Dashboard")).set({
        font: "title-14"
      });
      return dashboardLabel;
    },

    setPathButtons: function(nodeIds) {
      this.__mainViewCaptionLayout.removeAll();
      nodeIds.length === 1 ? this.__studyTitle.show() : this.__studyTitle.exclude();
      if (nodeIds.length === 0) {
        this.__highlightDashboard(true);
        return;
      }
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
          this.__highlightDashboard(false);
          btn.setFont("title-14");
        }
      }
    },

    __highlightDashboard: function(highlight = true) {
      this.__dashboardBtn.setFont(highlight ? "title-14" : "text-14");
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

    __createUserBtn: function() {
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

      const helpBtn = new qx.ui.menu.Button(this.tr("Help"));
      helpBtn.addListener("execute", () => window.open("https://docs.osparc.io"));
      osparc.utils.Utils.setIdToWidget(helpBtn, "userMenuHelpBtn");
      menu.add(helpBtn);

      const newIssueBtn = new qx.ui.menu.Button(this.tr("Open issue in GitHub"));
      newIssueBtn.addListener("execute", this.__openIssueInfoDialog, this);
      osparc.utils.Utils.setIdToWidget(newIssueBtn, "userMenuGithubBtn");
      menu.add(newIssueBtn);

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

      const userBtn = new qx.ui.form.MenuButton(null, null, menu);
      userBtn.getChildControl("icon").getContentElement()
        .setStyles({
          "border-radius": "16px"
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

    __openIssueInfoDialog: function() {
      const issueConfirmationWindow = new osparc.ui.window.Dialog("Information", null,
        this.tr("To create an issue in GitHub, you must have an account in GitHub and be already logged-in.")
      );
      const contBtn = new qx.ui.toolbar.Button(this.tr("Continue"), "@FontAwesome5Solid/external-link-alt/12");
      contBtn.addListener("execute", () => window.open(osparc.component.widget.NewGHIssue.getNewIssueUrl()), this);
      const loginBtn = new qx.ui.toolbar.Button(this.tr("Log in in GitHub"), "@FontAwesome5Solid/external-link-alt/12");
      loginBtn.addListener("execute", () => window.open("https://github.com/login"), this);
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
