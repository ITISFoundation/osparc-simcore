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

qx.Class.define("osparc.product.landingPage.s4llite.SolutionBase", {
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

  events: {
    "backToContent": "qx.event.type.Event"
  },

  statics: {
    createSolutionHeader: function(title, description) {
      const headerLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(20).set({
        alignX: "center",
        alignY: "middle"
      })).set({
        width: 450,
        maxWidth: 450
      });

      const text1 = new qx.ui.basic.Label().set({
        value: title,
        font: "text-26",
        rich: true,
        wrap: true
      });
      headerLayout.add(text1);

      const text2 = new qx.ui.basic.Label().set({
        value: description,
        font: "text-18",
        rich: true,
        wrap: true
      });
      headerLayout.add(text2);

      const label = qx.locale.Manager.tr("Request a Demo");
      const linkButton = this.mediumStrongButton(label);
      linkButton.getContentElement().setStyles({
        "border-radius": "8px"
      });
      linkButton.addListener("tap", () => window.open("https://zmt.swiss/", "_blank"));
      headerLayout.add(linkButton);

      return headerLayout;
    },

    mediumStrongButton: function(label) {
      const linkButton = new qx.ui.form.Button().set({
        appearance: "strong-button",
        label,
        font: "text-16",
        center: true,
        padding: 12,
        allowGrowX: false,
        width: 170
      });
      linkButton.getContentElement().setStyles({
        "border-radius": "8px"
      });
      return linkButton;
    }
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
      backToContentButton.addListener("execute", () => this.fireEvent("backToContent"));
      this._add(backToContentButton);


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
