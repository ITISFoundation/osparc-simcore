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
    });

    osparc.utils.Utils.setIdToWidget(this, "navigationBar");
  },

  events: {
    "backToDashboardPressed": "qx.event.type.Event",
    "downloadStudyLogs": "qx.event.type.Event"
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
    HEIGHT: 50,
    SMALL_SCREEN_BREAKPOINT: 800,

    BUTTON_OPTIONS: {
      font: "text-14",
      allowGrowY: false,
      minWidth: 30,
      minHeight: 30
    },

    PAGE_CONTEXT: {
      0: "dashboard",
      1: "workbench",
      2: "app"
    }
  },

  members: {
    __tabButtons: null,

    populateLayout: function() {
      this.__buildLayout();
      osparc.WindowSizeTracker.getInstance().addListener("changeCompactVersion", () => this.__navBarResized(), this);
    },

    __buildLayout: function() {
      this.getContentElement().setStyles({
        "background": "linear-gradient(0deg, rgba(1, 18, 26, 0.1) 0%, rgba(229, 229, 229, 0.1) 5%)"
      });
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

      // center-items
      this.getChildControl("read-only-info");

      // right-items
      this.getChildControl("tasks-button");
      this.getChildControl("notifications-button");
      this.getChildControl("expiration-icon");
      this.getChildControl("help");
      if (osparc.desktop.credits.Utils.areWalletsEnabled()) {
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
        case "credits-button":
          control = new osparc.desktop.credits.CreditsIndicatorButton();
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
          this.getChildControl("right-items").add(control);
          break;
        }
        case "help":
          control = this.__createHelpMenuBtn();
          control.set(this.self().BUTTON_OPTIONS);
          osparc.utils.Utils.setIdToWidget(control, "helpNavigationBtn");
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

    __createHelpMenuBtn: function() {
      const menu = new qx.ui.menu.Menu().set({
        position: "top-right"
      });
      const menuButton = new qx.ui.form.MenuButton(null, "@FontAwesome5Regular/question-circle/22", menu).set({
        backgroundColor: "transparent"
      });

      osparc.utils.Utils.setIdToWidget(menu, "helpNavigationMenu");

      // menus
      osparc.store.Support.addQuickStartToMenu(menu);
      osparc.store.Support.addGuidedToursToMenu(menu);
      osparc.store.Support.addManualButtonsToMenu(menu, menuButton);
      menu.addSeparator();

      // feedback
      osparc.store.Support.addSupportButtonsToMenu(menu, menuButton);

      osparc.utils.Utils.prettifyMenu(menu);

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
      this.bind("study", this.__tabButtons, "visibility", {
        converter: s => s ? "excluded" : "visible"
      });
      this.__navBarResized();
    },

    __applyStudy: function(study) {
      const readOnlyInfo = this.getChildControl("read-only-info")
      if (study) {
        this.getChildControl("study-title-options").setStudy(study);
        study.bind("readOnly", readOnlyInfo, "visibility", {
          converter: value => value ? "visible" : "excluded"
        });
      } else {
        readOnlyInfo.exclude();
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
        this.getChildControl("help").exclude();
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
        this.getChildControl("help").show();
        this.getChildControl("user-menu").show();
      }
    }
  }
});
