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

/**
 * Sandbox of static methods related to products.
 */

qx.Class.define("osparc.product.landingPage.Utils", {
  type: "static",

  statics: {
    titleLabel: function(text) {
      const label = new qx.ui.basic.Label().set({
        textAlign: "center",
        rich: true,
        wrap: true
      });
      if (text) {
        label.setValue(text);
      }
      return label;
    },

    smallTitle: function(text) {
      return this.self().titleLabel(text).set({
        font: "text-18",
        width: 200
      });
    },

    mediumTitle: function(text) {
      return this.self().titleLabel(text).set({
        font: "text-22",
        width: 550
      });
    },

    largeTitle: function(text) {
      return this.self().titleLabel(text).set({
        font: "text-26",
        width: 500
      });
    }
  }
});
