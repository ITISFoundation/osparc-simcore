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

    const navBar = new osparc.product.landingPage.NavigationBar();
    navBar.addListener("loginPressed", () => this.fireEvent("loginPressed"));
    this._add(navBar);

    const scrollContainer = new qx.ui.container.Scroll();
    const contentVBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(null, null, "separator-vertical"));

    const content = new osparc.product.landingPage.s4llite.Content();
    contentVBox.add(content);

    const footer = new osparc.product.landingPage.s4llite.Footer();
    contentVBox.add(footer);

    scrollContainer.add(contentVBox);
    this._add(scrollContainer, {
      flex: 1
    });

    const chat = osparc.product.landingPage.Chat.getInstance();
    const root = qx.core.Init.getApplication().getRoot();
    root.add(chat, {
      bottom: 20,
      right: 20
    });
  },

  events: {
    "loginPressed": "qx.event.type.Event"
  }
});
