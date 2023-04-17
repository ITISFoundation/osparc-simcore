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
        padding: 5,
        width: 90
      });
      backToContentButton.setMargin(30);
      backToContentButton.addListener("execute", () => this.fireEvent("backToContent"));
      this._add(backToContentButton);

      [
        "osparc/landingPage/diru1.png",
        "osparc/landingPage/diru2.png"
      ].forEach(imgSrc => {
        const img = new qx.ui.basic.Image(imgSrc);
        img.setMargin(30);
        img.getContentElement().setStyles({
          "border-radius": "6px"
        });
        this._add(img);
      });
    }
  }
});
