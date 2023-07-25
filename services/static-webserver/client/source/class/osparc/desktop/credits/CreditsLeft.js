/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.desktop.credits.CreditsLeft", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(3));

    this.set({
      padding: 5
    });

    this.__buildLayout();
  },

  members: {
    __buildLayout: function() {
      this.__addCredits();
    },

    __addCredits: function() {
      const store = osparc.store.Store.getInstance();
      store.getWallets().forEach(wallet => {
        const progressBar = new osparc.desktop.credits.CreditsIndicator(wallet, true).set({
          allowShrinkY: true
        });
        this._add(progressBar, {
          flex: 1
        });
      });
    }
  }
});
