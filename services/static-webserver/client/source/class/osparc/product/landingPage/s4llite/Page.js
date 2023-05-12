/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo (pcrespov)

************************************************************************ */

qx.Class.define("osparc.product.landingPage.s4llite.Page", {
  extend: qx.ui.core.Widget,

  /*
  *****************************************************************************
     CONSTRUCTOR
  *****************************************************************************
  */
  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(null, null, "separator-vertical"));

    const navBar = new osparc.product.landingPage.NavigationBar().set({
      backgroundColor: "background-main-2"
    });
    navBar.addListener("loginPressed", () => this.fireEvent("loginPressed"));
    this._add(navBar);

    const pagesStack = new qx.ui.container.Stack();

    // Marketing content
    const marketingScroll = new qx.ui.container.Scroll();
    const marketingLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(null, null, "separator-vertical"));
    const marketing = new osparc.product.landingPage.s4llite.Content();
    marketingLayout.add(marketing);
    const footer = new osparc.product.landingPage.s4llite.Footer().set({
      backgroundColor: "background-main-2"
    });
    marketingLayout.add(footer);
    marketingScroll.add(marketingLayout);
    pagesStack.add(marketingScroll);

    // Electromagnetics content
    const electromagneticsScroll = new qx.ui.container.Scroll();
    const electromagneticsLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(null, null, "separator-vertical"));
    const electromagnetics = new osparc.product.landingPage.s4llite.solutions.Electromagnetics();
    electromagneticsLayout.add(electromagnetics);
    const electromagneticsFooter = new osparc.product.landingPage.s4llite.Footer().set({
      backgroundColor: "background-main-2"
    });
    electromagneticsLayout.add(electromagneticsFooter);
    electromagneticsScroll.add(electromagneticsLayout);
    pagesStack.add(electromagneticsScroll);

    // NeuronalActivation content
    const neuronalActivationScroll = new qx.ui.container.Scroll();
    const neuronalActivationLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(null, null, "separator-vertical"));
    const neuronalActivation = new osparc.product.landingPage.s4llite.Pricing();
    neuronalActivationLayout.add(neuronalActivation);
    const neuronalActivationFooter = new osparc.product.landingPage.s4llite.Footer().set({
      backgroundColor: "background-main-2"
    });
    neuronalActivationLayout.add(neuronalActivationFooter);
    neuronalActivationScroll.add(neuronalActivationLayout);
    pagesStack.add(neuronalActivationScroll);

    // Pricing content
    const pricingScroll = new qx.ui.container.Scroll();
    const pricingLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(null, null, "separator-vertical"));
    const pricing = new osparc.product.landingPage.s4llite.Pricing();
    pricingLayout.add(pricing);
    const pricingFooter = new osparc.product.landingPage.s4llite.Footer().set({
      backgroundColor: "background-main-2"
    });
    pricingLayout.add(pricingFooter);
    pricingScroll.add(pricingLayout);
    pagesStack.add(pricingScroll);

    this._add(pagesStack, {
      flex: 1
    });

    navBar.addListener("showElectromagnetics", () => pagesStack.setSelection([electromagneticsScroll]));
    navBar.addListener("showNeuronalActivation", () => pagesStack.setSelection([neuronalActivationScroll]));
    navBar.addListener("showPricing", () => pagesStack.setSelection([pricingScroll]));
    navBar.addListener("showMainContent", () => pagesStack.setSelection([marketingScroll]));

    const chat = osparc.product.landingPage.Chat.getInstance();
    chat.start();
  },

  events: {
    "loginPressed": "qx.event.type.Event"
  },

  members: {
    close: function() {
      const chat = osparc.product.landingPage.Chat.getInstance();
      chat.stop();
    }
  }
});
