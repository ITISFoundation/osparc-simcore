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
    this._add(navBar);

    const scrollContainer = new qx.ui.container.Scroll();

    const content = new osparc.product.landingPage.s4llite.Content();
    content.setMinHeight(1000);
    scrollContainer.add(content);

    const footer = new osparc.product.landingPage.s4llite.Footer();
    scrollContainer.add(footer);

    this._add(scrollContainer, {
      flex: 1
    });
  },

  members: {
  }
});
