/* ************************************************************************

   qxapp - the simcore frontend

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
 *   let navBar = new qxapp.desktop.NavigationBar();
 *   this.getRoot().add(navBar);
 * </pre>
 */

const NAVIGATION_BUTTON_HEIGHT = 32;

qx.Class.define("qxapp.desktop.NavigationBar", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(10).set({
      alignY: "middle"
    }));

    this.set({
      paddingLeft: 10,
      paddingRight: 10,
      maxHeight: 50
    });

    const commonBtnSettings = {
      allowGrowY: false,
      minWidth: 32,
      minHeight: NAVIGATION_BUTTON_HEIGHT
    };

    let logo = qxapp.component.widget.LogoOnOff.getInstance();
    this._add(logo);
    this._add(new qx.ui.toolbar.Separator());

    let dashboardBtn = new qx.ui.form.Button(this.tr("Dashboard"));
    dashboardBtn.set(commonBtnSettings);
    dashboardBtn.addListener("execute", () => {
      this.fireEvent("dashboardPressed");
    }, this);
    this._add(dashboardBtn);

    this._add(new qx.ui.toolbar.Separator());

    let hBox = new qx.ui.layout.HBox(5).set({
      alignY: "middle"
    });
    let mainViewCaptionLayout = this.__mainViewCaptionLayout = new qx.ui.container.Composite(hBox);
    this._add(mainViewCaptionLayout);

    this._add(new qx.ui.core.Spacer(5), {
      flex: 1
    });

    const userEmail = qxapp.auth.Data.getInstance().getEmail() || "bizzy@itis.ethz.ch";
    const userName = qxapp.auth.Data.getInstance().getUserName() || "bizzy";
    let userLbl = new qx.ui.basic.Label(userName).set({
      minWidth: 10
    });
    this._add(userLbl);

    let userBtn = this.__createUserBtn();
    userBtn.set(commonBtnSettings);
    userBtn.set({
      decorator: new qx.ui.decoration.Decorator().set({
        radius: 50,
        backgroundImage: qxapp.utils.Avatar.getUrl(userEmail, NAVIGATION_BUTTON_HEIGHT)
      })
    });
    this._add(userBtn);
  },

  events: {
    "nodeDoubleClicked": "qx.event.type.Data",
    "dashboardPressed": "qx.event.type.Event"
  },

  properties: {
    project: {
      check: "qxapp.data.model.Project",
      nullable: true
    }
  },

  members: {
    __mainViewCaptionLayout: null,

    setPathButtons: function(nodeIds) {
      this.__mainViewCaptionLayout.removeAll();
      const navBarLabelFont = qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["nav-bar-label"]);
      for (let i=0; i<nodeIds.length; i++) {
        let btn = new qx.ui.form.Button().set({
          maxHeight: NAVIGATION_BUTTON_HEIGHT
        });
        const nodeId = nodeIds[i];
        if (nodeId === "root") {
          this.getProject().bind("name", btn, "label");
        } else {
          const node = this.getProject().getWorkbench()
            .getNode(nodeId);
          if (node) {
            node.bind("label", btn, "label");
          }
        }
        btn.addListener("execute", function() {
          this.fireDataEvent("nodeDoubleClicked", nodeId);
        }, this);
        this.__mainViewCaptionLayout.add(btn);

        if (i<nodeIds.length-1) {
          let mainViewCaption = this.__mainViewCaption = new qx.ui.basic.Label(">").set({
            font: navBarLabelFont
          });
          this.__mainViewCaptionLayout.add(mainViewCaption);
        }
      }
    },

    projectSaved: function() {
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

    __showMainViewCaptionAsText: function(newLabel) {
      const navBarLabelFont = qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["nav-bar-label"]);
      let mainViewCaption = this.__mainViewCaption = new qx.ui.basic.Label(newLabel).set({
        font: navBarLabelFont,
        minWidth: 150
      });
      this.__mainViewCaptionLayout.add(mainViewCaption);
    },

    __createUserBtn: function() {
      const menu = new qx.ui.menu.Menu();

      // Account Settings
      // ---
      // Help
      // About
      // ---
      // Logout

      // TODO: add commands (i.e. short-cut system)
      const preferences = new qx.ui.menu.Button(this.tr("Preferences"));
      preferences.addListener("execute", this.__onOpenAccountSettings, this);

      const logout = new qx.ui.menu.Button(this.tr("Logout"));
      logout.addListener("execute", e => {
        const app = qx.core.Init.getApplication();
        app.logout();
      });

      menu.add(preferences);
      menu.addSeparator();
      const newIssueBtn = new qx.ui.menu.Button(this.tr("Open issue"));
      newIssueBtn.addListener("execute", this.__onOpenNewIssueV0, this);
      menu.add(newIssueBtn);
      const helpBtn = new qx.ui.menu.Button(this.tr("Help"));
      helpBtn.addListener("execute", () => window.open("https://forum.zmt.swiss/"));
      menu.add(helpBtn);
      const aboutBtn = new qx.ui.menu.Button(this.tr("About"));
      aboutBtn.addListener("execute", () => qxapp.About.getInstance().open());
      menu.add(aboutBtn);
      menu.addSeparator();
      menu.add(logout);

      const btn = new qx.ui.form.MenuButton(null, null, menu);
      return btn;
    },

    __onOpenAccountSettings: function() {
      if (!this.__preferencesWin) {
        this.__preferencesWin = new qxapp.desktop.preferences.DialogWindow();
      }

      let win = this.__preferencesWin;
      if (win) {
        win.center();
        win.open();
      }
    },

    __onOpenNewIssueV0: function() {
      const issueDlg = new qxapp.component.widget.NewGHIssue();
      const win = new qx.ui.window.Window("Open New GitHub Issue").set({
        showMinimize: false,
        showMaximize: false,
        allowMaximize: false,
        showStatusbar: false,
        modal: true,
        width: 550,
        height: 300,
        layout: new qx.ui.layout.Canvas()
      });
      win.add(issueDlg, {
        top: 0,
        bottom: 0,
        left: 0,
        right: 0
      });
      win.center();
      win.open();
    }
  }
});
