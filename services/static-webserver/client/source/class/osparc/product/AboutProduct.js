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

    const displayName = osparc.store.StaticInfo.getDisplayName();
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
        case "s4lacad":
          this.__buildS4LLayout();
          break;
        case "s4llite":
          this.__buildS4LLiteLayout();
          break;
        case "tis":
        case "tiplite":
          this.__buildTIPLayout();
          break;
        default: {
          const noInfoText = this.tr("Information is unavailable");
          const noInfoLabel = osparc.product.quickStart.Utils.createLabel(noInfoText);
          this.add(noInfoLabel);
          break;
        }
      }
    },

    __buildS4LLayout: function() {
      const licenseUrl = osparc.store.Support.getLicenseURL();
      const introText = this.tr(
        "Sim4Life.web is a native implementation of the most advanced simulation platform, Sim4Life, in the cloud. " +
        "The platform empowers users to simulate, analyze, and predict complex, multifaceted, and dynamic biological interactions within the full anatomical complexity of the human body. " +
        "It provides the ability to set up and run complex simulations directly within any browser, utilizing cloud technology."
      );
      const sparcText = this.tr(
        "Sim4Life.web makes use of technologies developed by our research partner for the o<sup>2</sup>S<sup>2</sup>PARC platform, the IT’IS Foundation, and co-funded by the U.S. National Institutes of Health’s SPARC initiative."
      );
      const moreInfoText = this.tr("For more information about Sim4Life, please visit %1.", osparc.utils.Utils.createHTMLLink("sim4life.swiss", "https://sim4life.swiss/"));
      const licenseText = this.tr("To review license agreements, click %1.", osparc.utils.Utils.createHTMLLink("here", licenseUrl));
      const emailText = this.tr("Send us an email %1", this.__getMailTo());

      const text = [introText, "<br><br>", sparcText, "<br><br>", moreInfoText, "<br><br>", licenseText, "<br><br>", emailText].join("");
      const label = osparc.product.quickStart.Utils.createLabel(text);
      this.add(label);
    },

    __buildS4LLiteLayout: function() {
      // https://zurichmedtech.github.io/s4l-lite-manual/#/docs/what_is_s4l_lite
      const introText = this.tr("Sim4Life.lite is a powerful web-based simulation platform that allows you to model and analyze real-world phenomena and to design complex technical devices in a validated environment. With its intuitive interface and advanced tools, Sim4Life.lite makes it easy to develop your simulation project, wherever you are.");

      const licenseUrl = "https://zurichmedtech.github.io/s4l-lite-manual/#/docs/licensing/copyright_Sim4Life";
      const licenseText = this.tr("Click %1 to read the license agreements.", osparc.utils.Utils.createHTMLLink("here", licenseUrl));

      // more info ZMT website
      const moreInfoUrl = "https://zmt.swiss/";
      const moreInfoText = this.tr("For more information about Sim4Life.lite, visit %1.", osparc.utils.Utils.createHTMLLink("our website", moreInfoUrl));

      const emailText = this.tr("Send us an email %1", this.__getMailTo());

      [
        introText,
        licenseText,
        moreInfoText,
        emailText,
      ].forEach(text => {
        const label = osparc.product.quickStart.Utils.createLabel(text);
        this.add(label);
      });

      this.__addCopyright();
    },

    __buildTIPLayout: function() {
      const licenseUrl = osparc.store.Support.getLicenseURL();
      const introText = this.tr(
        "TIP (TI Planning Tool) is an innovative online platform designed to optimize targeted neurostimulation protocols using " +
        "temporal interference (TI) stimulation. Developed by IT'IS Foundation, TIP simplifies the complex process of planning deep " +
        "brain stimulation."
      );
      const poweredText = this.tr(
        "Powered by o<sup>2</sup>S<sup>2</sup>PARC technology, TIP utilizes sophisticated electromagnetic simulations, detailed anatomical head models, " +
        "and automated optimization to generate comprehensive reports with quantitative and visual information. This tool is " +
        "invaluable for neuroscientists and brain stimulation experts, especially those with limited computational modeling experience, " +
        "enabling them to create effective and safe stimulation protocols for their research."
      );
      const moreInfoText = this.tr("For more information about TIP, please visit %1.", osparc.utils.Utils.createHTMLLink("itis.swiss", "https://itis.swiss/tools-and-systems/ti-planning/overview"));
      const licenseText = this.tr("To review license agreements, click %1.", osparc.utils.Utils.createHTMLLink("here", licenseUrl));
      const emailText = this.tr("Send us an email %1", this.__getMailTo());

      const text = [introText, "<br><br>", poweredText, "<br><br>", moreInfoText, "<br><br>", licenseText, "<br><br>", emailText].join("");
      const label = osparc.product.quickStart.Utils.createLabel(text);
      this.add(label);
    },

    __getMailTo: function() {
      const supportEmail = osparc.store.VendorInfo.getSupportEmail();
      const productName = osparc.store.StaticInfo.getDisplayName();
      return osparc.store.Support.mailToLink(supportEmail, "Support " + productName, false);
    },

    __addCopyright: function() {
      const copyrightLink = new osparc.ui.basic.LinkLabel().set({
        font: "link-label-14"
      });
      const vendor = osparc.store.VendorInfo.getVendor();
      if (vendor && "url" in vendor && "copyright" in vendor) {
        copyrightLink.set({
          value: vendor.copyright,
          url: vendor.url
        });
      }
      this.add(copyrightLink);
    },
  }
});
