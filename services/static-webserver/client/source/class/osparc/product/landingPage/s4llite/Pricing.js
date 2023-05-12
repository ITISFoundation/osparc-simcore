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

    this._setLayout(new qx.ui.layout.VBox(20).set({
      alignX: "center",
      alignY: "middle"
    }));

    this.setPadding(30);

    this.buildLayout();
  },

  statics: {
    createToolbarRadioButton: function(label, icon, pos) {
      const rButton = new qx.ui.toolbar.RadioButton().set({
        label,
        icon,
        font: "text-18",
        padding: 15,
        gap: 10,
        paddingLeft: 20,
        paddingRight: 20,
        margin: 0
      });
      rButton.getContentElement().setStyles({
        "border-radius": "0px"
      });
      const radius = "12px";
      if (pos === "left") {
        rButton.getContentElement().setStyles({
          "border-top-left-radius": radius,
          "border-bottom-left-radius": radius
        });
      } else if (pos === "right") {
        rButton.getContentElement().setStyles({
          "border-top-right-radius": radius,
          "border-bottom-right-radius": radius
        });
      }
      return rButton;
    }
  },

  members: {
    buildLayout: function() {
      const toolbar = new qx.ui.toolbar.ToolBar().set({
        backgroundColor: "transparent"
      });
      const modePartLayout = new qx.ui.toolbar.Part();
      const cloudBtn = this.self().createToolbarRadioButton(this.tr("Cloud"), "@FontAwesome5Solid/cloud/36", "left");
      cloudBtn.addListener("execute", () => console.log("cloud"));

      const desktopBtn = this.self().createToolbarRadioButton(this.tr("Desktop"), "@FontAwesome5Solid/desktop/36", "right");
      desktopBtn.addListener("execute", () => console.log("desktop"));

      const radioGroup = new qx.ui.form.RadioGroup();
      [
        cloudBtn,
        desktopBtn
      ].forEach(btn => {
        modePartLayout.add(btn);
        radioGroup.add(btn);
      });
      radioGroup.setAllowEmptySelection(false);
      toolbar.addSpacer();
      toolbar.add(modePartLayout);
      toolbar.addSpacer();

      this._add(toolbar);


      const title1 = osparc.product.landingPage.Utils.largeTitle(this.tr("Pricing & Plans")).set({
        paddingTop: 20
      });
      this._add(title1);

      const img1 = new qx.ui.basic.Image("osparc/landingPage/diru1.png");
      img1.getContentElement().setStyles({
        "border-radius": "6px"
      });
      this._add(img1);

      const title2 = osparc.product.landingPage.Utils.largeTitle(this.tr("Choose the Right Plan for You")).set({
        paddingTop: 20
      });
      this._add(title2);

      const img2 = new qx.ui.basic.Image("osparc/landingPage/diru2.png");
      img2.getContentElement().setStyles({
        "border-radius": "6px"
      });
      this._add(img2);
    }
  }
});
