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

qx.Class.define("osparc.product.landingPage.s4llite.Pricing", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox().set({
      alignX: "center",
      alignY: "middle"
    }));

    this.buildLayout();
  },

  events: {
    "backToContent": "qx.event.type.Event"
  },

  members: {
    buildLayout: function() {
      const backToContentButton = new qx.ui.form.Button(this.tr("Back")).set({
        icon: "@FontAwesome5Solid/arrow-left/14",
        font: "text-14",
        alignX: "left",
        alignY: "middle",
        allowGrowX: false,
        padding: 10,
        width: 100
      });
      backToContentButton.setMargin(20);
      backToContentButton.addListener("execute", () => this.fireEvent("backToContent"));
      this._add(backToContentButton);

      const img1 = new qx.ui.basic.Image("osparc/landingPage/diru1.png");
      img1.setMargin(20);
      this._add(img1);

      const img2 = new qx.ui.basic.Image("osparc/landingPage/diru2.png");
      img2.setMargin(20);
      this._add(img2);
    }
  }
});
