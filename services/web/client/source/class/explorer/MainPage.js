/* ************************************************************************

   explorer - an entry point to oSparc

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("explorer.MainPage", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base();

    this._setLayout(new qx.ui.layout.VBox());

    const navBar = this.__navBar = new explorer.NavigationBar();
    navBar.buildLayout();
    this._add(navBar);

    const exploreBrowser = this.__exploreBrowser = new osparc.dashboard.ExploreBrowser();
    this._add(exploreBrowser, {
      flex: 1
    });
  }
});
