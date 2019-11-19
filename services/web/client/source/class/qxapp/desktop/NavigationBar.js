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
      maxHeight: 50,
      backgroundColor: "background-main-lighter"
    });

    const commonBtnSettings = {
      allowGrowY: false,
      minWidth: 32,
      minHeight: NAVIGATION_BUTTON_HEIGHT
    };

    let logo = qxapp.component.widget.LogoOnOff.getInstance();
    this._add(logo);
    this._add(new qx.ui.toolbar.Separator());

    let dashboardBtn = this.__dashboardBtn = new qx.ui.form.Button().set({
      rich: true
    });
    qxapp.utils.Utils.setIdToWidget(dashboardBtn, "dashboardBtn");
    dashboardBtn.set(commonBtnSettings);
    dashboardBtn.addListener("execute", () => {
      this.fireEvent("dashboardPressed");
    }, this);
    this.__highlightDashboard();
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

    this._add(new qxapp.ui.form.LinkButton(this.tr("User manual"), "https://docs.osparc.io").set({
      appearance: "link-button"
    }));

    this._add(new qxapp.ui.form.LinkButton(this.tr("Give us feedback"), this.self().FEEDBACK_FORM_URL).set({
      appearance: "link-button"
    }));

    const userEmail = qxapp.auth.Data.getInstance().getEmail() || "bizzy@itis.ethz.ch";
    const userName = qxapp.auth.Data.getInstance().getUserName() || "bizzy";

    const userBtn = this.__createUserBtn();
    userBtn.set({
      ...commonBtnSettings,
      icon: qxapp.utils.Avatar.getUrl(userEmail, NAVIGATION_BUTTON_HEIGHT),
      label: userName
    });

    this._add(userBtn);
  },

  events: {
    "nodeDoubleClicked": "qx.event.type.Data",
    "dashboardPressed": "qx.event.type.Event"
  },

  properties: {
    study: {
      check: "qxapp.data.model.Study",
      nullable: true
    }
  },

  statics: {
    FEEDBACK_FORM_URL: "https://docs.google.com/forms/d/e/1FAIpQLSe232bTigsM2zV97Kjp2OhCenl6o9gNGcDFt2kO_dfkIjtQAQ/viewform?usp=sf_link"
  },

  members: {
    __dashboardBtn: null,
    __mainViewCaptionLayout: null,

    setPathButtons: function(nodeIds) {
      this.__mainViewCaptionLayout.removeAll();
      const navBarLabelFont = qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["nav-bar-label"]);
      if (nodeIds.length === 0) {
        this.__highlightDashboard(true);
      }
      for (let i=0; i<nodeIds.length; i++) {
        let btn = new qx.ui.form.Button().set({
          rich: true,
          maxHeight: NAVIGATION_BUTTON_HEIGHT
        });
        const nodeId = nodeIds[i];
        if (nodeId === "root") {
          this.getStudy().bind("name", btn, "label");
        } else {
          const node = this.getStudy().getWorkbench()
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
        if (i === nodeIds.length-1) {
          this.__highlightDashboard(false);
          btn.setLabel("<b>" + btn.getLabel() + "</b>");
        }
      }
    },

    __highlightDashboard: function(highlight = true) {
      const label = this.tr("Dashboard");
      highlight ? this.__dashboardBtn.setLabel("<b>"+label+"</b>") : this.__dashboardBtn.setLabel(label);
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
      const menu = new qx.ui.menu.Menu();

      const preferences = new qx.ui.menu.Button(this.tr("Preferences"));
      preferences.addListener("execute", this.__onOpenAccountSettings, this);
      qxapp.utils.Utils.setIdToWidget(preferences, "userMenuPreferencesBtn");
      menu.add(preferences);

      menu.addSeparator();

      const helpBtn = new qx.ui.menu.Button(this.tr("Help"));
      helpBtn.addListener("execute", () => window.open("https://docs.osparc.io"));
      qxapp.utils.Utils.setIdToWidget(helpBtn, "userMenuHelpBtn");
      menu.add(helpBtn);

      const newIssueBtn = new qx.ui.menu.Button(this.tr("Open issue in GitHub"));
      newIssueBtn.addListener("execute", () => window.open(qxapp.component.widget.NewGHIssue.getNewIssueUrl()));
      qxapp.utils.Utils.setIdToWidget(newIssueBtn, "userMenuGithubBtn");
      menu.add(newIssueBtn);

      const aboutBtn = new qx.ui.menu.Button(this.tr("About"));
      aboutBtn.addListener("execute", () => qxapp.About.getInstance().open());
      qxapp.utils.Utils.setIdToWidget(aboutBtn, "userMenuAboutBtn");
      menu.add(aboutBtn);

      menu.addSeparator();

      const logout = new qx.ui.menu.Button(this.tr("Logout"));
      logout.addListener("execute", e => {
        qx.core.Init.getApplication().logout();
      });
      qxapp.utils.Utils.setIdToWidget(logout, "userMenuLogoutBtn");
      menu.add(logout);

      const userBtn = new qx.ui.form.MenuButton(null, null, menu);
      userBtn.getChildControl("icon").getContentElement()
        .setStyles({
          "border-radius": "16px"
        });
      qxapp.utils.Utils.setIdToWidget(userBtn, "userMenuMainBtn");

      return userBtn;
    },

    __onOpenAccountSettings: function() {
      if (!this.__preferencesWin) {
        this.__preferencesWin = new qxapp.desktop.preferences.Preferences();
      }

      let win = this.__preferencesWin;
      if (win) {
        win.center();
        win.open();
      }
    }
  }
});
