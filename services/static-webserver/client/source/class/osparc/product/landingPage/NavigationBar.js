/* ************************************************************************

   osparc - an entry point to oSparc

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.product.landingPage.NavigationBar", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(20).set({
      alignY: "middle"
    }));

    this.set({
      paddingLeft: 10,
      paddingRight: 10,
      height: osparc.navigation.NavigationBar.HEIGHT
    });

    this.buildLayout();
  },

  events: {
    "showPricing": "qx.event.type.Event",
    "loginPressed": "qx.event.type.Event"
  },

  statics: {
    addEntryToMenu: function(menu, entryText) {
      const entryButton = new qx.ui.menu.Button(entryText);
      entryButton.getChildControl("label").set({
        rich: true
      });
      menu.add(entryButton);
      return entryButton;
    }
  },

  members: {
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
        case "on-logo": {
          control = new osparc.ui.basic.LogoWPlatform().set({
            cursor: "pointer"
          });
          control.setSize({
            width: 100,
            height: 50
          });
          control.getChildControl("logo").addListener("tap", () => window.location.reload());
          control.setFont("text-9");
          this.getChildControl("left-items").add(control);
          break;
        }
        case "logo-powered":
          control = new osparc.ui.basic.PoweredByOsparc().set({
            width: 50,
            padding: 3,
            paddingTop: 1,
            maxHeight: 50
          });
          this.getChildControl("left-items").add(control);
          break;
        case "products":
          control = this.__createProductsMenuBtn();
          control.set(osparc.navigation.NavigationBar.BUTTON_OPTIONS);
          this.getChildControl("right-items").add(control);
          break;
        case "solutions":
          control = this.__createSolutionsMenuBtn();
          control.set(osparc.navigation.NavigationBar.BUTTON_OPTIONS);
          this.getChildControl("right-items").add(control);
          break;
        case "resources":
          control = this.__createResourcesMenuBtn();
          control.set(osparc.navigation.NavigationBar.BUTTON_OPTIONS);
          this.getChildControl("right-items").add(control);
          break;
        case "gallery":
          control = this.__createGalleryMenuBtn();
          control.set(osparc.navigation.NavigationBar.BUTTON_OPTIONS);
          this.getChildControl("right-items").add(control);
          break;
        case "success-stories":
          control = this.__createSuccessStoriesBtn();
          control.set(osparc.navigation.NavigationBar.BUTTON_OPTIONS);
          this.getChildControl("right-items").add(control);
          break;
        case "pricing":
          control = this.__createPricingBtn();
          control.set(osparc.navigation.NavigationBar.BUTTON_OPTIONS);
          this.getChildControl("right-items").add(control);
          break;
        case "theme-switch":
          control = new osparc.ui.switch.ThemeSwitcherFormBtn().set({
            toolTipText: this.tr("Switch theme")
          });
          control.set(osparc.navigation.NavigationBar.BUTTON_OPTIONS);
          this.getChildControl("right-items").add(control);
          break;
        case "login-button": {
          control = this.__createLoginBtn();
          control.set(osparc.navigation.NavigationBar.BUTTON_OPTIONS);
          this.getChildControl("right-items").add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    buildLayout: function() {
      this.getChildControl("left-items");
      this.getChildControl("center-items");
      this.getChildControl("right-items");

      this.getChildControl("on-logo").setSize({
        width: 100,
        height: 50
      });
      if (!osparc.product.Utils.isProduct("osparc")) {
        this.getChildControl("logo-powered");
      }

      this.getChildControl("products");
      this.getChildControl("solutions");
      this.getChildControl("resources");
      this.getChildControl("gallery");
      this.getChildControl("success-stories");
      this.getChildControl("pricing");
      this.getChildControl("theme-switch");
      this.getChildControl("login-button");
    },

    __createProductsMenuBtn: function() {
      const menu = new qx.ui.menu.Menu().set({
        font: "text-14"
      });
      const menuButton = new osparc.ui.form.HoverMenuButton().set({
        label: this.tr("Products"),
        menu
      });
      this.self().addEntryToMenu(menu, "Cloud platform");
      this.self().addEntryToMenu(menu, "Desktop");
      this.self().addEntryToMenu(menu, "Electromagnetics");
      this.self().addEntryToMenu(menu, "Neuronal activation");
      this.self().addEntryToMenu(menu, "Thermodynamics");
      this.self().addEntryToMenu(menu, "Acoustics");
      this.self().addEntryToMenu(menu, "Computational human phantoms");
      this.self().addEntryToMenu(menu, "CAD Modeling");
      return menuButton;
    },

    __createSolutionsMenuBtn: function() {
      const menu = new qx.ui.menu.Menu().set({
        font: "text-14"
      });
      const menuButton = new osparc.ui.form.HoverMenuButton().set({
        label: this.tr("Solutions"),
        menu
      });
      this.self().addEntryToMenu(menu, "Industries");
      this.self().addEntryToMenu(menu, "Academia");
      this.self().addEntryToMenu(menu, "Applications");
      return menuButton;
    },

    __createResourcesMenuBtn: function() {
      const menu = new qx.ui.menu.Menu().set({
        font: "text-14"
      });
      const menuButton = new osparc.ui.form.HoverMenuButton().set({
        label: this.tr("Resources"),
        menu
      });
      this.self().addEntryToMenu(menu, "News");
      this.self().addEntryToMenu(menu, "Demos");
      this.self().addEntryToMenu(menu, "Tutorials");
      this.self().addEntryToMenu(menu, "Documentation");
      this.self().addEntryToMenu(menu, "Computable Human Models (ViP)");
      const button = this.self().addEntryToMenu(menu, "Forum");
      button.addListener("execute", () => window.open("https://forum.zmt.swiss/"));
      this.self().addEntryToMenu(menu, "Python API");
      this.self().addEntryToMenu(menu, "Validation");
      this.self().addEntryToMenu(menu, "Security");
      this.self().addEntryToMenu(menu, "Whitepapers");
      return menuButton;
    },

    __createGalleryMenuBtn: function() {
      const menu = new qx.ui.menu.Menu().set({
        font: "text-14"
      });
      const menuButton = new osparc.ui.form.HoverMenuButton().set({
        label: this.tr("Gallery"),
        menu
      });
      this.self().addEntryToMenu(menu, "Industries");
      this.self().addEntryToMenu(menu, "Academia");
      this.self().addEntryToMenu(menu, "Applications");
      return menuButton;
    },

    __createSuccessStoriesBtn: function() {
      const pricingButton = new qx.ui.form.Button().set({
        label: this.tr("Success stories"),
        backgroundColor: "transparent"
      });
      return pricingButton;
    },

    __createPricingBtn: function() {
      const pricingButton = new qx.ui.form.Button().set({
        label: this.tr("Pricing"),
        backgroundColor: "transparent"
      });
      pricingButton.addListener("execute", () => this.fireEvent("showPricing"));
      return pricingButton;
    },

    __createLoginBtn: function() {
      const loginButton = new qx.ui.form.Button().set({
        label: this.tr("Log in"),
        icon: "@FontAwesome5Solid/edit/14",
        appearance: "strong-button"
      });
      osparc.utils.Utils.setIdToWidget(loginButton, "toLogInPage");
      loginButton.addListener("execute", () => this.fireEvent("loginPressed"));
      return loginButton;
    }
  }
});
