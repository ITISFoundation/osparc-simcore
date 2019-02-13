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

/* eslint no-warning-comments: "off" */

const NAVIGATION_BUTTON_HEIGHT = 32;

qx.Class.define("qxapp.desktop.NavigationBar", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base(arguments, new qx.ui.layout.HBox());

    this.set({
      paddingLeft: 10,
      paddingRight: 10,
      maxHeight: 50
    });
    this.getLayout().set({
      spacing: 10,
      alignY: "middle"
    });

    const commonBtnSettings = {
      allowGrowY: false,
      minWidth: 32,
      minHeight: NAVIGATION_BUTTON_HEIGHT
    };

    let logo = qxapp.component.widget.LogoOnOff.getInstance();
    this.add(logo);

    this.add(new qx.ui.toolbar.Separator());

    let hBox = new qx.ui.layout.HBox(5).set({
      alignY: "middle"
    });
    let mainViewCaptionLayout = this.__mainViewCaptionLayout = new qx.ui.container.Composite(hBox);
    this.add(mainViewCaptionLayout);


    this.add(new qx.ui.core.Spacer(5), {
      flex: 1
    });


    let dashboardBtn = new qx.ui.form.Button(this.tr("Dashboard"));
    dashboardBtn.set(commonBtnSettings);
    dashboardBtn.addListener("execute", () => {
      this.fireEvent("dashboardPressed");
    }, this);
    this.add(dashboardBtn);

    this.add(new qx.ui.toolbar.Separator());

    let forumBtn = new qx.ui.form.Button(this.tr("Forum"));
    forumBtn.addListener("execute", () => {
      window.open("https://forum.zmt.swiss/");
    }, this);
    forumBtn.set(commonBtnSettings);
    this.add(forumBtn);

    this.add(new qx.ui.toolbar.Separator());

    let helpBtn = new qx.ui.form.Button(this.tr("Help"));
    helpBtn.set(commonBtnSettings);
    this.add(helpBtn);

    this.add(new qx.ui.toolbar.Separator());

    const userEmail = qxapp.auth.Data.getInstance().getEmail() || "bizzy@itis.ethz.ch";
    const userName = qxapp.auth.Data.getInstance().getUserName() || "bizzy";

    let userLbl = new qx.ui.basic.Label(userName).set({
      minWidth: 10
    });
    this.add(userLbl);

    let userBtn = this.__createUserBtn();
    userBtn.set(commonBtnSettings);
    userBtn.set({
      decorator: new qx.ui.decoration.Decorator().set({
        radius: 50,
        backgroundImage: qxapp.utils.Avatar.getUrl(userEmail, NAVIGATION_BUTTON_HEIGHT)
      })
    });
    this.add(userBtn);
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

    setMainViewCaption: function(newLabel) {
      this.__mainViewCaptionLayout.removeAll();
      if (typeof newLabel === "string") {
        this.__showMainViewCaptionAsText(newLabel);
      } else if (Array.isArray(newLabel)) {
        this.__showMainViewCaptionAsButtons(newLabel);
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

    __showMainViewCaptionAsButtons: function(nodeIds) {
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

    __createUserBtn: function() {
      var menu = new qx.ui.menu.Menu();

      // Account Settings
      // ---
      // Groups
      // ---
      // Help
      // Report a Problem
      // About
      // ---
      // Logout

      // TODO: add commands (i.e. short-cut system)
      let preferences = new qx.ui.menu.Button(this.tr("Preferences"));
      preferences.addListener("execute", this.__onOpenAccountSettings, this);

      let logout = new qx.ui.menu.Button(this.tr("Logout"));
      logout.addListener("execute", e => {
        let app = qx.core.Init.getApplication();
        app.logout();
      });

      menu.add(preferences);
      menu.addSeparator();
      menu.add(new qx.ui.menu.Button(this.tr("Groups")));
      menu.addSeparator();
      menu.add(new qx.ui.menu.Button(this.tr("Help")));
      menu.add(new qx.ui.menu.Button(this.tr("Report a Problem")));
      let aboutBtn = new qx.ui.menu.Button(this.tr("About"));
      aboutBtn.addListener("execute", e => qxapp.About.getInstance().open());
      menu.add(aboutBtn);
      menu.addSeparator();
      menu.add(logout);

      let btn = new qx.ui.form.MenuButton(null, null, menu);
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
    }
  }
});
