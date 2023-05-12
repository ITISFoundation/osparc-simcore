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
    "showMainContent": "qx.event.type.Event",
    "showElectromagnetics": "qx.event.type.Event",
    "showNeuronalActivation": "qx.event.type.Event",
    "showPricing": "qx.event.type.Event",
    "loginPressed": "qx.event.type.Event"
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

    __createEntryInMenu: function(menu, entryText, addToMainContentListener = true) {
      const button = new qx.ui.menu.Button(entryText);
      button.getChildControl("label").set({
        rich: true
      });
      if (addToMainContentListener) {
        button.addListener("execute", () => this.fireEvent("showMainContent"));
      }
      menu.add(button);
      return button;
    },

    __createButton: function(entryText, addToMainContentListener = true) {
      const button = new qx.ui.form.Button(entryText).set({
        rich: true,
        backgroundColor: "transparent"
      });
      if (addToMainContentListener) {
        button.addListener("execute", () => this.fireEvent("showMainContent"));
      }
      return button;
    },

    __createProductsMenuBtn: function() {
      const menu = new qx.ui.menu.Menu().set({
        font: "text-14"
      });
      const menuButton = new osparc.ui.form.HoverMenuButton().set({
        label: this.tr("Products"),
        menu
      });
      this.__createEntryInMenu(menu, "Cloud platform");
      this.__createEntryInMenu(menu, "Desktop");
      const electromagneticsButton = this.__createEntryInMenu(menu, "Electromagnetics", false);
      electromagneticsButton.addListener("execute", () => this.fireEvent("showElectromagnetics"));
      const neuronalActivationButton = this.__createEntryInMenu(menu, "Neuronal activation", false);
      neuronalActivationButton.addListener("execute", () => this.fireEvent("showNeuronalActivation"));
      this.__createEntryInMenu(menu, "Thermodynamics");
      this.__createEntryInMenu(menu, "Acoustics");
      this.__createEntryInMenu(menu, "Computational human phantoms");
      this.__createEntryInMenu(menu, "CAD Modeling");
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

      const industriesMenuBtn = this.__createEntryInMenu(menu, "Industries");
      const industriesMenu = new qx.ui.menu.Menu().set({
        font: "text-14",
        padding: 10,
        backgroundColor: "background-main-1"
      });
      industriesMenu.getContentElement().setStyles({
        "border-width": "0px"
      });
      [
        "Medical Implants",
        "Telecommunications",
        "Automotive",
        "Wearable devices",
        "Neurotechnologies"
      ].forEach(label => this.__createEntryInMenu(industriesMenu, label));
      industriesMenuBtn.setMenu(industriesMenu);

      const accademiaMenuBtn = this.__createEntryInMenu(menu, "Accademia");
      const accademiaMenu = new qx.ui.menu.Menu().set({
        font: "text-14",
        padding: 10,
        backgroundColor: "background-main-1"
      });
      accademiaMenu.getContentElement().setStyles({
        "border-width": "0px"
      });
      [
        "Students",
        "Research"
      ].forEach(label => this.__createEntryInMenu(accademiaMenu, label));
      accademiaMenuBtn.setMenu(accademiaMenu);

      const applicationsMenuBtn = this.__createEntryInMenu(menu, "Applications");
      const applicationsMenu = new qx.ui.menu.Menu().set({
        font: "text-14",
        padding: 10,
        backgroundColor: "background-main-1"
      });
      applicationsMenu.getContentElement().setStyles({
        "border-width": "0px"
      });
      [
        "Neuro stimulation",
        "MRI implant safety",
        "Antenna design",
        "SAR compliance",
        "mmWave exposure",
        "Thermal therapies",
        "Wireless power transfer",
        "FUS",
        "Wearables"
      ].forEach(label => this.__createEntryInMenu(applicationsMenu, label));
      applicationsMenuBtn.setMenu(applicationsMenu);

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
      this.__createEntryInMenu(menu, "News");
      this.__createEntryInMenu(menu, "Demos");
      this.__createEntryInMenu(menu, "Tutorials");
      this.__createEntryInMenu(menu, "Documentation");
      this.__createEntryInMenu(menu, "Computable Human Models (ViP)");
      const button = this.__createEntryInMenu(menu, "Forum");
      button.addListener("execute", () => window.open("https://forum.zmt.swiss/"));
      this.__createEntryInMenu(menu, "Python API");
      this.__createEntryInMenu(menu, "Validation");
      this.__createEntryInMenu(menu, "Security");
      this.__createEntryInMenu(menu, "Whitepapers");
      return menuButton;
    },

    __createGalleryMenuBtn: function() {
      const galleryButton = this.__createButton(this.tr("Gallery"));
      return galleryButton;
    },

    __createSuccessStoriesBtn: function() {
      const successStoriesButton = this.__createButton(this.tr("Success stories"));
      return successStoriesButton;
    },

    __createPricingBtn: function() {
      const pricingButton = this.__createButton(this.tr("Pricing"), false);
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
