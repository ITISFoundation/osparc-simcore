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
      backgroundColor: "background-main-1"
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
    __serverStatics: null,

    buildLayout: function() {
      this.getChildControl("left-items");
      this.getChildControl("center-items");
      this.getChildControl("right-items");

      this.getChildControl("logo");

      this.getChildControl("dashboard-button");
      this.getChildControl("dashboard-label");

      this.getChildControl("read-only-icon");

      this.getChildControl("tasks-button");
      this.getChildControl("expiration-icon");
      this.getChildControl("manual");
      this.getChildControl("feedback");
      this.getChildControl("theme-switch");
      this.getChildControl("user-menu");

      this.setPageContext("dashboard");

      setTimeout(() => this.__checkScreenSize(), 100);
      window.addEventListener("resize", () => this.__checkScreenSize());
    },

    __checkScreenSize: function() {
      const h = document.documentElement.clientHeight;
      this.setHeight(h > 900 ? 60 : 50);

      const logo = this.getChildControl("logo");

      logo.getChildControl("off-logo").set({
        width: h > 900 ? 110 : 100,
        height: h > 900 ? 45 : 35
      });

      logo.getChildControl("on-logo").setSize({
        width: h > 900 ? 110 : 100,
        height: h > 900 ? 60 : 50
      });
    },

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "left-items":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(30).set({
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
          control = osparc.component.widget.LogoOnOff.getInstance();
          this.getChildControl("left-items").add(control);
          break;
        case "dashboard-button":
          control = new osparc.ui.form.FetchButton(this.tr("Dashboard"), "@FontAwesome5Solid/home/16").set({
            ...this.self().BUTTON_OPTIONS,
            font: "title-14"
          });
          osparc.utils.Utils.setIdToWidget(control, "dashboardBtn");
          control.addListener("execute", () => this.fireEvent("backToDashboardPressed"), this);
          this.getChildControl("left-items").add(control);
          break;
        case "dashboard-label":
          control = new qx.ui.basic.Label(this.tr("Dashboard")).set({
            paddingLeft: 20, // to align it with the button
            font: "text-14"
          });
          this.getChildControl("left-items").add(control);
          break;
        case "study-menu-info":
          control = new qx.ui.menu.Button().set({
            label: this.tr("Information..."),
            icon: "@MaterialIcons/info_outline/14",
            ...this.self().BUTTON_OPTIONS
          });
          control.addListener("execute", () => {
            const infoMerged = new osparc.info.MergedLarge(this.getStudy());
            const title = this.tr("Information");
            const width = 600;
            const height = 700;
            osparc.ui.window.Window.popUpInWindow(infoMerged, title, width, height);
          });
          break;
        case "study-menu-download-logs":
          control = new qx.ui.menu.Button().set({
            label: this.tr("Download logs"),
            icon: "@FontAwesome5Solid/download/14",
            ...this.self().BUTTON_OPTIONS
          });
          control.addListener("execute", () => this.fireEvent("downloadStudyLogs"));
          break;
        case "study-menu-button": {
          const optionsMenu = new qx.ui.menu.Menu();
          optionsMenu.add(this.getChildControl("study-menu-info"));
          optionsMenu.add(this.getChildControl("study-menu-download-logs"));
          control = new qx.ui.form.MenuButton().set({
            ...this.self().BUTTON_OPTIONS,
            menu: optionsMenu,
            icon: "@FontAwesome5Solid/ellipsis-v/16"
          });
          this.getChildControl("left-items").add(control);
          break;
        }
        case "edit-title-label":
          control = new osparc.ui.form.EditLabel().set({
            labelFont: "text-16",
            inputFont: "text-16"
          });
          control.addListener("editValue", e => {
            const newLabel = e.getData();
            this.getStudy().setName(newLabel);
          });
          this.getChildControl("left-items").add(control);
          break;
        case "read-only-icon":
          control = new qx.ui.basic.Image("@FontAwesome5Solid/eye/22").set({
            visibility: "excluded",
            paddingRight: 10,
            toolTipText: "Read Only"
          });
          this.getChildControl("center-items").add(control);
          break;
        case "tasks-button":
          control = new osparc.component.task.TasksButton();
          this.getChildControl("right-items").add(control);
          break;
        case "expiration-icon":
          control = new qx.ui.basic.Image("@FontAwesome5Solid/hourglass-end/22").set({
            visibility: "excluded",
            textColor: "danger-red",
            cursor: "pointer"
          });
          control.addListener("tap", () => osparc.navigation.UserMenuButton.openPreferences(), this);
          osparc.auth.Data.getInstance().bind("expirationDate", control, "visibility", {
            converter: expirationDay => {
              if (expirationDay) {
                const now = new Date();
                const today = new Date(now.toISOString().slice(0, 10));
                const daysToExpiration = osparc.utils.Utils.daysBetween(today, expirationDay);
                if (daysToExpiration < 7) {
                  osparc.utils.Utils.expirationMessage(daysToExpiration)
                    .then(msg => control.setToolTipText(msg));
                  return "visible";
                }
              }
              return "excluded";
            }
          });
          this.getChildControl("right-items").add(control);
          break;
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
          control = new osparc.ui.switch.ThemeSwitcherFormBtn();
          control.set(this.self().BUTTON_OPTIONS);
          this.getChildControl("right-items").add(control);
          break;
        case "user-menu":
          control = new osparc.navigation.UserMenuButton();
          control.populateSimpleMenu();
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
          if (osparc.utils.Utils.isProduct("s4llite")) {
            this.getChildControl("study-menu-button").exclude();
            this.getChildControl("edit-title-label").exclude();
          }
          this.getChildControl("read-only-icon").exclude();
          if (this.__tabButtons) {
            this.__tabButtons.show();
          }
          break;
        case "workbench":
        case "guided":
        case "app":
          this.getChildControl("dashboard-label").exclude();
          this.getChildControl("dashboard-button").show();
          if (osparc.utils.Utils.isProduct("s4llite")) {
            this.getChildControl("study-menu-button").show();
            this.getStudy().bind("name", this.getChildControl("edit-title-label"), "value");
            this.getChildControl("edit-title-label").show();
          }
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
        toolTipText: this.tr("Manuals")
      });
      osparc.store.Support.addManualButtonsToMenu(menu, menuButton);
      return menuButton;
    },

    __createFeedbackMenuBtn: function() {
      const menu = new qx.ui.menu.Menu().set({
        font: "text-14"
      });
      const menuButton = new qx.ui.form.MenuButton(null, "@FontAwesome5Solid/comments/22", menu).set({
        toolTipText: this.tr("Support")
      });
      osparc.store.Support.addSupportButtonsToMenu(menu, menuButton);
      return menuButton;
    },

    addDashboardTabButtons: function(tabButtons) {
      this.__tabButtons = tabButtons;
      this.getChildControl("center-items").add(tabButtons);
    },

    _applyStudy: function(study) {
      if (study) {
        study.bind("readOnly", this.getChildControl("read-only-icon"), "visibility", {
          converter: value => value ? "visible" : "excluded"
        });
      }
    }
  }
});
