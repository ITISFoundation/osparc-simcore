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
      this.getChildControl("avatar-group");
      this.getChildControl("tasks-button");
      if (osparc.product.Utils.showComputationalActivity()) {
        this.getChildControl("jobs-button");
      }
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
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(6).set({
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
            alignY: "middle",
          });;
          this.getChildControl("right-items").add(control);
          break;
        }
        case "tasks-button":
          control = new osparc.task.TasksButton().set({
            visibility: "excluded",
            ...this.self().RIGHT_BUTTON_OPTS
          });
          this.getChildControl("right-items").add(control);
          break;
        case "jobs-button":
          control = new osparc.jobs.JobsButton().set({
            ...this.self().RIGHT_BUTTON_OPTS
          });
          this.getChildControl("right-items").add(control);
          break;
        case "notifications-button":
          control = new osparc.notification.NotificationsButton().set({
            ...this.self().RIGHT_BUTTON_OPTS
          });
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
          control = this.__createHelpMenuBtn().set({
            ...this.self().RIGHT_BUTTON_OPTS
          });
          osparc.utils.Utils.setIdToWidget(control, "helpNavigationBtn");
          this.getChildControl("right-items").add(control);
          break;
        case "credits-button":
          control = new osparc.desktop.credits.CreditsIndicatorButton().set({
            ...this.self().RIGHT_BUTTON_OPTS
          });
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

    __listenToProjectStateUpdated: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();
      socket.on("projectStateUpdated", data => {
        if (this.getStudy() && data["project_uuid"] === this.getStudy().getUuid()) {
          const projectState = data["data"];
          const currentUserGroupIds = osparc.study.Utils.state.getCurrentGroupIds(projectState);
          // remove myself from the list of users
          const filteredUserGroupIds = currentUserGroupIds.filter(gid => gid !== osparc.store.Groups.getInstance().getMyGroupId());
          // show the rest of the users in the avatar group
          const avatarGroup = this.getChildControl("avatar-group");
          avatarGroup.setUserGroupIds(filteredUserGroupIds);
        }
      }, this);
    },

    __createHelpMenuBtn: function() {
      const menu = new qx.ui.menu.Menu().set({
        position: "top-right",
        appearance: "menu-wider",
      });
      const menuButton = new qx.ui.form.MenuButton(null, "@FontAwesome5Regular/question-circle/22", menu).set({
        backgroundColor: "transparent"
      });

      osparc.utils.Utils.setIdToWidget(menu, "helpNavigationMenu");

      // quick starts and manuals
      osparc.store.Support.addQuickStartToMenu(menu);
      osparc.store.Support.addGuidedToursToMenu(menu);
      osparc.store.Support.addManualButtonsToMenu(menu, menuButton);
      menu.addSeparator();

      // feedback
      osparc.store.Support.addSupportButtonsToMenu(menu, menuButton);
      osparc.store.Support.addReleaseNotesToMenu(menu);

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
      const savingStudyIcon = this.getChildControl("saving-study-icon");
      const readOnlyInfo = this.getChildControl("read-only-info");
      const avatarGroup = this.getChildControl("avatar-group");
      if (study) {
        this.getChildControl("study-title-options").setStudy(study);
        study.bind("savePending", savingStudyIcon, "visibility", {
          converter: value => value && ["workbench", "pipeline"].includes(study.getUi().getMode()) ? "visible" : "excluded"
        });
        study.bind("readOnly", readOnlyInfo, "visibility", {
          converter: value => value ? "visible" : "excluded"
        });
        avatarGroup.show();
      } else {
        savingStudyIcon.exclude();
        readOnlyInfo.exclude();
        avatarGroup.exclude();
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
