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

    const displayName = osparc.store.StaticInfo.getInstance().getDisplayName();
    this.setCaption(this.tr("About ") + displayName);

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

    this.__buildLayout();
  },

  statics: {
    WIDTH: 500,
    PADDING: 15
  },

  members: {
    __buildLayout: function() {
      switch (osparc.product.Utils.getProductName()) {
        case "s4l":
          this.__buildS4LLayout();
          break;
        case "s4lacad":
          this.__buildS4LAcademicLayout();
          break;
        case "s4llite":
          this.__buildS4LLiteLayout();
          break;
        default: {
          const noInfoText = this.tr("Information not available");
          const noInfoLabel = osparc.product.quickStart.Utils.createLabel(noInfoText);
          this.add(noInfoLabel);
          break;
        }
      }
    },

    __buildS4LLayout: function() {
      osparc.store.Support.getLicenseURL()
        .then(licenseUrl => {
          const color = qx.theme.manager.Color.getInstance().resolve("text");
          const text = this.tr(`
            sim4life.io is a native implementation of the most advanced simulation platform, Sim4Life, in the cloud. \
            The platform empowers users to simulate, analyze, and predict complex, multifaceted, and dynamic biological interactions within the full anatomical complexity of the human body. \
            It provides the ability to set up and run complex simulations directly within any browser, utilizing cloud technology.
            <br><br>
            sim4life.io makes use of technologies developed by our research partner for the o<sup>2</sup>S<sup>2</sup>PARC platform, the IT’IS Foundation, and co-funded by the U.S. National Institutes of Health’s SPARC initiative.\
            <br><br>
            For more information about Sim4Life, please visit <a href='https://sim4life.swiss/' style='color: ${color}' target='_blank'>sim4life.swiss</a>.
            <br><br>
            To review license agreements, click <a href=${licenseUrl} style='color: ${color}' target='_blank'>here</a>.
          `);

          const label = osparc.product.quickStart.Utils.createLabel(text);
          this.add(label);
        });
    },

    __buildS4LAcademicLayout: function() {
      osparc.store.Support.getLicenseURL()
        .then(licenseUrl => {
          const color = qx.theme.manager.Color.getInstance().resolve("text");
          const text = this.tr(`
            sim4life.science is a native implementation of the most advanced simulation platform, Sim4Life, in the cloud. \
            The platform empowers users to simulate, analyze, and predict complex, multifaceted, and dynamic biological interactions within the full anatomical complexity of the human body. \
            It provides the ability to set up and run complex simulations directly within any browser, utilizing cloud technology.
            <br><br>
            sim4life.science makes use of technologies developed by our research partner for the o<sup>2</sup>S<sup>2</sup>PARC platform, the IT’IS Foundation, and co-funded by the U.S. National Institutes of Health’s SPARC initiative.\
            <br><br>
            For more information about Sim4Life, please visit <a href='https://sim4life.swiss/' style='color: ${color}' target='_blank'>sim4life.swiss</a>.
            <br><br>
            To review license agreements, click <a href=${licenseUrl} style='color: ${color}' target='_blank'>here</a>.
          `);

          const label = osparc.product.quickStart.Utils.createLabel(text);
          this.add(label);
        });
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
        const label = osparc.product.quickStart.Utils.createLabel(text);
        this.add(label);
      });

      this.__addCopyright();
    },

    __addCopyright: function() {
      const copyrightLink = new osparc.ui.basic.LinkLabel().set({
        font: "link-label-14"
      });
      const vendor = osparc.store.VendorInfo.getInstance().getVendor();
      if (vendor && "url" in vendor && "copyright" in vendor) {
        copyrightLink.set({
          value: vendor.copyright,
          url: vendor.url
        });
      }
      this.add(copyrightLink);
    }
  }
});
