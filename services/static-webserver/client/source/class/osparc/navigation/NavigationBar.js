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
      backgroundColor: "background-main-1"
    });

    osparc.data.Resources.get("notifications")
      .then(notifications => {
        osparc.notification.Notifications.getInstance().addNotifications(notifications);
        this.buildLayout();
        this.setPageContext("dashboard");
        osparc.WindowSizeTracker.getInstance().addListener("changeCompactVersion", () => this.__navBarResized(), this);
      });
  },

  events: {
    "backToDashboardPressed": "qx.event.type.Event",
    "downloadStudyLogs": "qx.event.type.Event"
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      nullable: true,
      event: "changeStudy",
      apply: "_applyStudy"
    },

    pageContext: {
      check: ["dashboard", "workbench", "guided", "app"],
      nullable: false,
      apply: "_applyPageContext"
    }
  },

  statics: {
    HEIGHT: 50,
    SMALL_SCREEN_BREAKPOINT: 800,

    BUTTON_OPTIONS: {
      font: "text-14",
      allowGrowY: false,
      minWidth: 32,
      minHeight: 32
    },

    PAGE_CONTEXT: {
      0: "dashboard",
      1: "workbench",
      2: "app"
    }
  },

  members: {
    __tabButtons: null,

    buildLayout: function() {
      this.getChildControl("left-items");
      this.getChildControl("center-items");
      this.getChildControl("right-items");

      // left-items
      this.getChildControl("logo");
      if (!osparc.product.Utils.isProduct("osparc")) {
        this.getChildControl("logo-powered");
      }

      this.getChildControl("dashboard-label");
      this.getChildControl("dashboard-button");

      // center-items
      this.getChildControl("read-only-info");

      // right-items
      if (osparc.desktop.credits.Utils.areWalletsEnabled()) {
        this.getChildControl("current-usage-indicator");
        this.getChildControl("wallets-viewer");
      }
      this.getChildControl("tasks-button");
      this.getChildControl("notifications-button");
      this.getChildControl("expiration-icon");
      this.getChildControl("manual");
      this.getChildControl("feedback");
      this.getChildControl("theme-switch");
      this.getChildControl("log-in-button");
      this.getChildControl("user-menu");
    },

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "left-items":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(20).set({
            alignY: "middle",
            alignX: "left"
          }));
          this._addAt(control, 0);
          break;
        case "center-items":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
            alignY: "middle",
            alignX: "center"
          }));
          this._addAt(control, 1, {
            flex: 1
          });
          break;
        case "right-items":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
            alignY: "middle",
            alignX: "right"
          }));
          this._addAt(control, 2);
          break;
        case "logo":
          control = osparc.navigation.LogoOnOff.getInstance().set({
            alignY: "middle"
          });
          control.getChildControl("off-logo").set({
            width: 100,
            height: 35
          });
          control.getChildControl("on-logo").setSize({
            width: osparc.product.Utils.getProductName() === "s4l" ? 150 : 100,
            height: osparc.navigation.NavigationBar.HEIGHT
          });
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
          osparc.utils.Utils.setIdToWidget(control, "dashboardBtn");
          control.addListener("execute", () => this.fireEvent("backToDashboardPressed"), this);
          this.getChildControl("left-items").add(control);
          break;
        case "dashboard-label":
          control = new qx.ui.basic.Label(this.tr("Dashboard")).set({
            paddingLeft: 10,
            font: "text-14"
          });
          osparc.utils.Utils.setIdToWidget(control, "dashboardLabel");
          this.getChildControl("left-items").add(control);
          break;
        case "study-title-options":
          control = new osparc.navigation.StudyTitleWOptions();
          control.addListener("downloadStudyLogs", () => this.fireEvent("downloadStudyLogs"));
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
        case "current-usage-indicator": {
          const currentUsage = new osparc.desktop.credits.CurrentUsage();
          control = new osparc.desktop.credits.CurrentUsageIndicator(currentUsage).set({
            allowGrowY: false,
            alignY: "middle"
          });
          this.getChildControl("right-items").add(control);
          break;
        }
        case "wallets-viewer":
          control = new osparc.desktop.credits.WalletsMiniViewer().set({
            maxHeight: this.self().HEIGHT
          });
          this.getChildControl("right-items").add(control);
          break;
        case "tasks-button":
          control = new osparc.task.TasksButton();
          this.getChildControl("right-items").add(control);
          break;
        case "notifications-button":
          control = new osparc.notification.NotificationsButton();
          this.getChildControl("right-items").add(control);
          break;
        case "expiration-icon": {
          control = new qx.ui.basic.Image("@FontAwesome5Solid/hourglass-end/22").set({
            visibility: "excluded",
            textColor: "danger-red",
            cursor: "pointer"
          });
          control.addListener("tap", () => osparc.desktop.credits.UserCenterWindow.openWindow(), this);
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
          this.getChildControl("right-items").add(control);
          break;
        }
        case "manual":
          control = this.__createManualMenuBtn();
          control.set(this.self().BUTTON_OPTIONS);
          this.getChildControl("right-items").add(control);
          break;
        case "feedback":
          control = this.__createFeedbackMenuBtn();
          control.set(this.self().BUTTON_OPTIONS);
          this.getChildControl("right-items").add(control);
          break;
        case "theme-switch":
          control = new osparc.ui.switch.ThemeSwitcherFormBtn().set({
            toolTipText: this.tr("Switch theme")
          });
          control.set(this.self().BUTTON_OPTIONS);
          this.getChildControl("right-items").add(control);
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
          this.getChildControl("right-items").add(control);
          break;
        }
        case "user-menu":
          control = new osparc.navigation.UserMenuButton();
          control.populateMenu();
          control.set(this.self().BUTTON_OPTIONS);
          this.getChildControl("right-items").add(control);
          break;
        case "user-menu-compact":
          control = new osparc.navigation.UserMenuButton();
          control.populateMenuCompact();
          control.set(this.self().BUTTON_OPTIONS);
          this.getChildControl("right-items").add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    _applyPageContext: function(newCtxt) {
      switch (newCtxt) {
        case "dashboard":
          this.getChildControl("dashboard-label").show();
          this.getChildControl("dashboard-button").exclude();
          this.getChildControl("study-title-options").exclude();
          this.getChildControl("read-only-info").exclude();
          if (this.__tabButtons) {
            this.__tabButtons.show();
          }
          break;
        case "workbench":
        case "guided":
        case "app":
          this.getChildControl("dashboard-label").exclude();
          this.getChildControl("dashboard-button").show();
          this.getChildControl("study-title-options").show();
          if (this.__tabButtons) {
            this.__tabButtons.exclude();
          }
          break;
      }
    },

    __createManualMenuBtn: function() {
      const menu = new qx.ui.menu.Menu().set({
        font: "text-14"
      });
      const menuButton = new qx.ui.form.MenuButton(null, "@FontAwesome5Solid/book/22", menu).set({
        toolTipText: this.tr("Manuals"),
        backgroundColor: "transparent"
      });
      osparc.store.Support.addQuickStartToMenu(menu);
      osparc.store.Support.addGuidedToursToMenu(menu);
      osparc.store.Support.addManualButtonsToMenu(menu, menuButton);
      osparc.utils.Utils.setIdToWidget(menuButton, "manualsButton");
      osparc.utils.Utils.setIdToWidget(menu, "manualsMenu");
      return menuButton;
    },

    __createFeedbackMenuBtn: function() {
      const menu = new qx.ui.menu.Menu().set({
        font: "text-14"
      });
      const menuButton = new qx.ui.form.MenuButton(null, "@FontAwesome5Solid/comments/22", menu).set({
        toolTipText: this.tr("Support"),
        backgroundColor: "transparent"
      });
      osparc.store.Support.addSupportButtonsToMenu(menu, menuButton);
      osparc.utils.Utils.setIdToWidget(menuButton, "feedbackButton");
      osparc.utils.Utils.setIdToWidget(menu, "feedbackMenu");
      return menuButton;
    },

    __createLoginBtn: function() {
      const registerButton = new qx.ui.form.Button(this.tr("Log in"), "@FontAwesome5Solid/edit/14");
      registerButton.addListener("execute", () => window.open(window.location.href, "_blank"));
      return registerButton;
    },

    addDashboardTabButtons: function(tabButtons) {
      this.__tabButtons = tabButtons;
      this.getChildControl("center-items").add(tabButtons);
      this.__navBarResized();
    },

    _applyStudy: function(study) {
      if (study) {
        study.bind("readOnly", this.getChildControl("read-only-info"), "visibility", {
          converter: value => value ? "visible" : "excluded"
        });
        this.getChildControl("study-title-options").setStudy(study);
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
        this.getChildControl("manual").exclude();
        this.getChildControl("feedback").exclude();
        this.getChildControl("theme-switch").exclude();
        this.getChildControl("user-menu-compact").show();
      } else {
        // left-items
        this.getChildControl("logo").getChildControl("on-logo").setSize({
          width: osparc.product.Utils.getProductName() === "s4l" ? 150 : 100,
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
        this.getChildControl("manual").show();
        this.getChildControl("feedback").show();
        this.getChildControl("theme-switch").show();
        this.getChildControl("user-menu").show();
      }
    }
  }
});
