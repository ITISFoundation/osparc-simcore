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

    const navBar = this.__navBar = this.__createNavigationBar();
    this._add(navBar);

    const exploreBrowser = this.__exploreBrowser = this.__createMainView();
    this._add(exploreBrowser, {
      flex: 1
    });
  },

  members: {
    __navBar: null,
    __exploreBrowser: null,

    __createNavigationBar: function() {
      const navBar = new explorer.NavigationBar();
      navBar.buildLayout();
      return navBar;
    },

    __createMainView: function() {
      const exploreBrowser = new osparc.dashboard.ExploreBrowser().set({
        alignX: "center",
        maxWidth: osparc.desktop.MainPage.MIN_STUDIES_PER_ROW * (osparc.dashboard.GridButtonBase.ITEM_WIDTH + osparc.dashboard.GridButtonBase.SPACING) + 8 // padding + scrollbar
      });
      return exploreBrowser;
    }
  }
});
