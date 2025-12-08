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

    this._setLayout(new qx.ui.layout.HBox(20).set({
      alignY: "middle"
    }));

    this.set({
      paddingLeft: 10,
      paddingRight: 10,
      height: this.self().HEIGHT,
      backgroundColor: this.self().BG_COLOR,
    });

    osparc.utils.Utils.setIdToWidget(this, "navigationBar");

    const socket = osparc.wrapper.WebSocket.getInstance();
    if (socket.isConnected()) {
      this.__listenToProjectStateUpdated();
    } else {
      socket.addListener("connect", () => this.__listenToProjectStateUpdated());
    }
  },

  events: {
    "backToDashboardPressed": "qx.event.type.Event",
    "openLogger": "qx.event.type.Event"
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      nullable: true,
      init: null,
      event: "changeStudy",
      apply: "__applyStudy"
    }
  },

  statics: {
    BG_COLOR: "background-main-1",
    HEIGHT: 50,
    SMALL_SCREEN_BREAKPOINT: 800,

    BUTTON_OPTIONS: {
      font: "text-14",
      allowGrowY: false,
      minWidth: 30,
      minHeight: 30
    },

    RIGHT_BUTTON_POS: {
      AVATARS: 0,
      EXPIRATION: 1,
      TASKS: 2,
      JOBS: 3,
      NOTIFICATIONS: 4,
      HELP: 5,
      CREDITS: 6,
      LOGIN: 7,
      USER_MENU: 8,
      USER_MENU_COMPACT: 9,
    },

    RIGHT_BUTTON_OPTS: {
      cursor: "pointer",
      alignX: "center",
      alignY: "middle",
      allowGrowX: false,
      allowGrowY: false,
      padding: 4,
    },
  },

  members: {
    __tabButtons: null,

    populateLayout: function() {
      this.__buildLayout();
      osparc.WindowSizeTracker.getInstance().addListener("changeCompactVersion", () => this.__navBarResized(), this);
    },

    __buildLayout: function() {
      this.getChildControl("left-items");
      this.getChildControl("center-items");
      this.getChildControl("right-items");

      // left-items
      this.getChildControl("logo");
      if (!osparc.product.Utils.isProduct("osparc")) {
        this.getChildControl("logo-powered");
      }

      const dashboardBtn = this.getChildControl("dashboard-button");
      this.bind("study", dashboardBtn, "visibility", {
        converter: s => s ? "visible" : "excluded"
      });

      const studyTitleOptions = this.getChildControl("study-title-options");
      this.bind("study", studyTitleOptions, "visibility", {
        converter: s => s ? "visible" : "excluded"
      });

      this.getChildControl("saving-study-icon");

      // center-items
      this.getChildControl("read-only-info");

      // right-items
      if (osparc.utils.DisabledPlugins.isRTCEnabled()) {
        this.getChildControl("avatar-group");
      }
      this.getChildControl("expiration-icon");
      this.getChildControl("tasks-button");
      if (osparc.product.Utils.showComputationalActivity()) {
        this.getChildControl("jobs-button");
      }
      this.getChildControl("notifications-button");
      this.getChildControl("help-button");
      if (osparc.store.StaticInfo.isBillableProduct()) {
        this.getChildControl("credits-button");
      }
      this.getChildControl("log-in-button");
      this.getChildControl("user-menu");
    },

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "left-items":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(20).set({
            alignX: "left",
            alignY: "middle",
          }));
          this._addAt(control, 0, { flex: 1 });
          break;
        case "center-items":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
            alignX: "center",
            alignY: "middle",
          }));
          this._addAt(control, 1);
          break;
        case "right-items":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(6).set({
            alignX: "right",
            alignY: "middle",
          }));
          this._addAt(control, 2, { flex: 1 });
          break;
        case "logo":
          control = osparc.navigation.LogoOnOff.getInstance().set({
            alignY: "middle"
          });
          control.getChildControl("off-logo").set({
            width: 92,
            height: 35,
            scale: true
          })
          control.getChildControl("on-logo").setSize({
            width: osparc.product.Utils.isS4LProduct() ? 150 : 100,
            height: osparc.navigation.NavigationBar.HEIGHT
          });
          if (osparc.product.Utils.isProduct("tiplite")) {
            control.set({
              cursor: "pointer",
              toolTipText: this.tr("This is TIP.lite, a light version of TIP.<br>Request access to TIP.")
            });
            control.addListener("tap", () => osparc.product.TIPTeaser.getInstance().open());
          }
          this.getChildControl("left-items").add(control);
          break;
        case "logo-powered":
          control = new osparc.ui.basic.PoweredByOsparc().set({
            padding: 3,
            paddingTop: 2,
            maxHeight: this.self().HEIGHT - 5
          });
          this.getChildControl("left-items").add(control);
          break;
        case "dashboard-button":
          control = new osparc.ui.form.FetchButton(this.tr("Dashboard"), "@FontAwesome5Solid/home/16").set({
            ...this.self().BUTTON_OPTIONS
          });
          control.set({
            appearance: "fab-button"
          });
          osparc.utils.Utils.setIdToWidget(control, "dashboardBtn");
          control.addListener("execute", () => this.fireEvent("backToDashboardPressed"), this);
          this.getChildControl("left-items").add(control);
          break;
        case "study-title-options":
          control = new osparc.navigation.StudyTitleWOptions();
          control.addListener("openLogger", () => this.fireEvent("openLogger"));
          this.getChildControl("left-items").add(control);
          break;
        case "saving-study-icon":
          control = new qx.ui.basic.Atom().set({
            icon: "@FontAwesome5Solid/cloud-upload-alt/14",
            label: this.tr("Saving..."),
            font: "text-12",
            opacity: 0.8,
            visibility: "excluded",
          });
          osparc.utils.Utils.setIdToWidget(control, "savingStudyIcon");
          this.getChildControl("left-items").add(control);
          break;
        case "read-only-info": {
          control = new qx.ui.basic.Atom().set({
            label: this.tr("Read only"),
            icon: "@FontAwesome5Solid/eye/22",
            gap: 10,
            font: "text-14",
            visibility: "excluded"
          });
          const hint = new osparc.ui.hint.Hint(control, osparc.desktop.StudyEditor.READ_ONLY_TEXT).set({
            active: false
          });
          hint.getLabel().set({
            maxWidth: 300,
            font: "text-14"
          });
          control.addListenerOnce("appear", () => hint.attachShowHideHandlers());
          this.getChildControl("center-items").add(control);
          break;
        }
        case "avatar-group": {
          const maxWidth = osparc.WindowSizeTracker.getInstance().isCompactVersion() ? 80 : 150;
          control = new osparc.ui.basic.AvatarGroup(26, "right", maxWidth).set({
            hideMyself: true,
            alignY: "middle",
            visibility: "excluded",
          });
          this.getChildControl("right-items").addAt(control, this.self().RIGHT_BUTTON_POS.AVATARS);
          break;
        }
        case "expiration-icon": {
          control = new qx.ui.basic.Image("@FontAwesome5Solid/hourglass-end/22").set({
            visibility: "excluded",
            textColor: "danger-red",
            cursor: "pointer"
          });
          control.addListener("tap", () => osparc.desktop.account.MyAccountWindow.openWindow(), this);
          const authData = osparc.auth.Data.getInstance();
          authData.bind("expirationDate", control, "visibility", {
            converter: expirationDay => {
              if (expirationDay && !authData.isGuest()) {
                const now = new Date();
                const today = new Date(now.toISOString().slice(0, 10));
                const daysToExpiration = osparc.utils.Utils.daysBetween(today, expirationDay);
                if (daysToExpiration < 7) {
                  const msg = osparc.utils.Utils.expirationMessage(daysToExpiration);
                  control.setToolTipText(msg);
                  return "visible";
                }
              }
              return "excluded";
            }
          });
          this.getChildControl("right-items").addAt(control, this.self().RIGHT_BUTTON_POS.EXPIRATION);
          break;
        }
        case "tasks-button":
          control = new osparc.task.TasksButton().set({
            ...this.self().RIGHT_BUTTON_OPTS
          });
          this.getChildControl("right-items").addAt(control, this.self().RIGHT_BUTTON_POS.TASKS);
          break;
        case "jobs-button":
          control = new osparc.jobs.JobsButton().set({
            ...this.self().RIGHT_BUTTON_OPTS
          });
          this.getChildControl("right-items").addAt(control, this.self().RIGHT_BUTTON_POS.JOBS);
          break;
        case "notifications-button":
          control = new osparc.notification.NotificationsButton().set({
            ...this.self().RIGHT_BUTTON_OPTS
          });
          this.getChildControl("right-items").addAt(control, this.self().RIGHT_BUTTON_POS.NOTIFICATIONS);
          break;
        case "help-button":
          control = new osparc.support.SupportButton().set({
            ...this.self().RIGHT_BUTTON_OPTS
          });
          this.getChildControl("right-items").addAt(control, this.self().RIGHT_BUTTON_POS.HELP);
          break;
        case "credits-button":
          control = new osparc.desktop.credits.CreditsIndicatorButton().set({
            ...this.self().RIGHT_BUTTON_OPTS
          });
          this.getChildControl("right-items").addAt(control, this.self().RIGHT_BUTTON_POS.CREDITS);
          break;
        case "log-in-button": {
          control = this.__createLoginBtn().set({
            visibility: "excluded"
          });
          control.set(this.self().BUTTON_OPTIONS);
          const authData = osparc.auth.Data.getInstance();
          authData.bind("guest", control, "visibility", {
            converter: isGuest => isGuest ? "visible" : "excluded"
          });
          this.getChildControl("right-items").addAt(control, this.self().RIGHT_BUTTON_POS.LOGIN);
          break;
        }
        case "user-menu":
          control = new osparc.navigation.UserMenuButton();
          control.populateMenu();
          control.set(this.self().BUTTON_OPTIONS);
          this.getChildControl("right-items").addAt(control, this.self().RIGHT_BUTTON_POS.USER_MENU);
          break;
        case "user-menu-compact":
          control = new osparc.navigation.UserMenuButton();
          control.populateMenuCompact();
          control.set(this.self().BUTTON_OPTIONS);
          this.getChildControl("right-items").addAt(control, this.self().RIGHT_BUTTON_POS.USER_MENU_COMPACT);
          break;
      }
      return control || this.base(arguments, id);
    },

    __listenToProjectStateUpdated: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();
      socket.on("projectStateUpdated", data => {
        if (osparc.utils.DisabledPlugins.isRTCEnabled()) {
          if (this.getStudy() && data["project_uuid"] === this.getStudy().getUuid()) {
            const projectState = data["data"];
            const currentUserGroupIds = osparc.study.Utils.state.getCurrentGroupIds(projectState);
            const avatarGroup = this.getChildControl("avatar-group");
            avatarGroup.setUserGroupIds(currentUserGroupIds);
          }
        }
      }, this);
    },

    __createLoginBtn: function() {
      const registerButton = new qx.ui.form.Button(this.tr("Log in"), "@FontAwesome5Solid/edit/14");
      registerButton.addListener("execute", () => window.open(window.location.href, "_blank"));
      return registerButton;
    },

    addDashboardTabButtons: function(tabButtons) {
      this.__tabButtons = tabButtons;
      this.getChildControl("center-items").add(tabButtons);
      this.bind("study", this.__tabButtons, "visibility", {
        converter: s => s ? "excluded" : "visible"
      });
      this.__navBarResized();
    },

    __applyStudy: function(study) {
      const savingStudyIcon = this.getChildControl("saving-study-icon");
      const readOnlyInfo = this.getChildControl("read-only-info");
      if (study) {
        this.getChildControl("study-title-options").setStudy(study);
        study.bind("savePending", savingStudyIcon, "visibility", {
          converter: value => value && ["workbench", "pipeline"].includes(study.getUi().getMode()) ? "visible" : "excluded"
        });
        study.bind("readOnly", readOnlyInfo, "visibility", {
          converter: value => value ? "visible" : "excluded"
        });
      } else {
        savingStudyIcon.exclude();
        readOnlyInfo.exclude();
      }

      if (osparc.utils.DisabledPlugins.isRTCEnabled()) {
        const avatarGroup = this.getChildControl("avatar-group");
        if (study) {
          avatarGroup.show();
        } else {
          avatarGroup.exclude();
          avatarGroup.setUserGroupIds([]);
        }
      }
    },

    __navBarResized: function() {
      let tabButtons = [];
      if (this.__tabButtons) {
        tabButtons = this.__tabButtons.getChildControl("content").getChildren();
      }
      if (osparc.WindowSizeTracker.getInstance().isCompactVersion()) {
        // left-items
        this.getChildControl("logo").getChildControl("on-logo").setSize({
          width: 100,
          height: osparc.navigation.NavigationBar.HEIGHT
        });
        if (!osparc.product.Utils.isProduct("osparc")) {
          this.getChildControl("logo-powered").exclude();
        }

        // center-items
        tabButtons.forEach(tabButton => {
          tabButton.getChildControl("icon").show();
          tabButton.getChildControl("label").exclude();
          tabButton.setToolTipText(tabButton.ttt);
        });

        // right-items
        this.getChildControl("user-menu").exclude();
        this.getChildControl("help-button").exclude();
        this.getChildControl("user-menu-compact").show();
      } else {
        // left-items
        this.getChildControl("logo").getChildControl("on-logo").setSize({
          width: osparc.product.Utils.isS4LProduct() ? 150 : 100,
          height: osparc.navigation.NavigationBar.HEIGHT
        });
        if (!osparc.product.Utils.isProduct("osparc")) {
          this.getChildControl("logo-powered").show();
        }

        // center-items
        tabButtons.forEach(tabButton => {
          tabButton.getChildControl("label").show();
          tabButton.getChildControl("icon").exclude();
          tabButton.resetToolTipText();
        });

        // right-items
        this.getChildControl("user-menu-compact").exclude();
        this.getChildControl("help-button").show();
        this.getChildControl("user-menu").show();
      }
    }
  }
});
