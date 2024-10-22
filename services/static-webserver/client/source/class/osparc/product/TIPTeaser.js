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

qx.Class.define("osparc.product.TIPTeaser", {
  extend: osparc.ui.window.Window,
  type: "singleton",

  construct: function() {
    this.base(arguments, this.tr("Access Full TIP"));

    this.set({
      layout: new qx.ui.layout.VBox(10),
      width: this.self().WIDTH,
      contentPadding: this.self().PADDING,
      showMaximize: false,
      showMinimize: false,
      resizable: true,
      centerOnAppear: true,
      clickAwayClose: true,
      modal: true
    });

    this.getChildControl("teaser-text");

    osparc.utils.Utils.setIdToWidget(this, "tipTeaserWindow");

    const closeBtn = this.getChildControl("close-button");
    osparc.utils.Utils.setIdToWidget(closeBtn, "tipTeaserWindowCloseBtn");
  },

  statics: {
    WIDTH: 500,
    PADDING: 15
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "teaser-text": {
          const link1 = osparc.utils.Utils.createHTMLLink("Request Full TIP Access", "https://tip.science/");
          const link2 = osparc.utils.Utils.createHTMLLink("Learn More About EAP", "https://temporalinterference.com/");
          const text = this.tr(`
            Unlock the Full Potential of TI Research!<br>
            <br>
            Are you part of the TI Solutions Early Adopter Program (EAP)?<br>
            <br>
            If yes, you have free access to our complete TIP platform with advanced features for TI planning and simulations. Click here to request access.<br>
            <br>
            Not an EAP member yet? Join our cutting-edge research community:<br>
            • Use our investigational TIBS-R devices in your projects<br>
            • Contribute to advancing TI knowledge<br>
            • Shape the future of neurostimulation technology<br>
            <br>
            Click here to learn more about EAP and apply today!<br>
            <br>
            ${link1}&nbsp&nbsp&nbsp${link2}
          `);
          control = new qx.ui.basic.Label(text).set({
            font: "text-14",
            wrap: true,
            rich: true,
          });
          this.add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },
  }
});
