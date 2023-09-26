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

qx.Class.define("osparc.product.AboutProduct", {
  extend: osparc.ui.window.Window,
  type: "singleton",

  construct: function() {
    this.base(arguments, this.tr("About Product"));

    osparc.store.StaticInfo.getInstance().getDisplayName()
      .then(displayName => {
        this.setCaption(this.tr("About ") + displayName);
      });

    this.set({
      layout: new qx.ui.layout.VBox(10),
      minWidth: this.self().MIN_WIDTH,
      maxWidth: this.self().MAX_WIDTH,
      contentPadding: this.self().PADDING,
      showMaximize: false,
      showMinimize: false,
      resizable: false,
      centerOnAppear: true,
      clickAwayClose: true,
      modal: true
    });

    this.__buildLayout();
  },

  statics: {
    MIN_WIDTH: 200,
    MAX_WIDTH: 400,
    PADDING: 15
  },

  members: {
    __buildLayout: function() {
      switch (osparc.product.Utils.getProductName()) {
        case "s4l":
          this.__buildS4LLayout();
          break;
        case "s4llite":
          this.__buildS4LLiteLayout();
          break;
        case "s4lacad":
          this.__buildS4LAcademicLayout();
          break;
        default: {
          const noInfoText = this.tr("Information not available");
          const noInfoLabel = osparc.product.tutorial.Utils.createLabel(noInfoText).set({
            maxWidth: this.self().MAX_WIDTH - 2*this.self().PADDING
          });
          this.add(noInfoLabel);
          break;
        }
      }
    },

    __buildS4LLayout: function() {
      const color = qx.theme.manager.Color.getInstance().resolve("text");

      const introText = "TODO: Intro text";

      const licenseUrl = "";
      const licenseText = `TODO: Click <a href=${licenseUrl} style='color: ${color}' target='_blank'>here</a> to read the license agreements.`;

      // more info ZMT website
      const moreInfoUrl = "https://zmt.swiss/";
      const moreInfoText = `For more information about <i>S4L</i>, visit <a href=${moreInfoUrl} style='color: ${color}' target='_blank'>our website</a>.`;

      [
        introText,
        licenseText,
        moreInfoText
      ].forEach(text => {
        const label = osparc.product.tutorial.Utils.createLabel(text).set({
          maxWidth: this.self().MAX_WIDTH - 2*this.self().PADDING
        });
        this.add(label);
      });

      this.__addCopyright();
    },

    __buildS4LLiteLayout: function() {
      const color = qx.theme.manager.Color.getInstance().resolve("text");

      // https://zurichmedtech.github.io/s4l-lite-manual/#/docs/what_is_s4l_lite
      const introText = "<i>S4L<sup>lite</sup></i> is a powerful web-based simulation platform that allows you to model and analyze real-world phenomena and to design complex technical devices in a validated environment. With its intuitive interface and advanced tools, <i>S4L<sup>lite</sup></i> makes it easy to develop your simulation project, wherever you are.";

      const licenseUrl = "https://zurichmedtech.github.io/s4l-lite-manual/#/docs/licensing/copyright_Sim4Life";
      const licenseText = `Click <a href=${licenseUrl} style='color: ${color}' target='_blank'>here</a> to read the license agreements.`;

      // more info ZMT website
      const moreInfoUrl = "https://zmt.swiss/";
      const moreInfoText = `For more information about <i>S4L<sup>lite</sup></i>, visit <a href=${moreInfoUrl} style='color: ${color}' target='_blank'>our website</a>.`;

      [
        introText,
        licenseText,
        moreInfoText
      ].forEach(text => {
        const label = osparc.product.tutorial.Utils.createLabel(text).set({
          maxWidth: this.self().MAX_WIDTH - 2*this.self().PADDING
        });
        this.add(label);
      });

      this.__addCopyright();
    },

    __buildS4LAcademicLayout: function() {
      const color = qx.theme.manager.Color.getInstance().resolve("text");

      const introText = "TODO: Intro text";

      const licenseUrl = "";
      const licenseText = `TODO: Click <a href=${licenseUrl} style='color: ${color}' target='_blank'>here</a> to read the license agreements.`;

      // more info ZMT website
      const moreInfoUrl = "https://zmt.swiss/";
      const moreInfoText = `For more information about <i>S4L Academic</i>, visit <a href=${moreInfoUrl} style='color: ${color}' target='_blank'>our website</a>.`;

      [
        introText,
        licenseText,
        moreInfoText
      ].forEach(text => {
        const label = osparc.product.tutorial.Utils.createLabel(text).set({
          maxWidth: this.self().MAX_WIDTH - 2*this.self().PADDING
        });
        this.add(label);
      });

      this.__addCopyright();
    },

    __addCopyright: function() {
      const copyrightLink = new osparc.ui.basic.LinkLabel().set({
        font: "link-label-14"
      });
      osparc.store.VendorInfo.getInstance().getVendor()
        .then(vendor => {
          if (vendor) {
            copyrightLink.set({
              value: vendor.copyright,
              url: vendor.url
            });
          }
        });
      this.add(copyrightLink);
    }
  }
});
