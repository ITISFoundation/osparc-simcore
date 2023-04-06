/* ************************************************************************

   osparc - an entry point to oSparc

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.product.landingPage.s4llite.Footer", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(20).set({
      alignY: "middle"
    }));

    this.set({
      padding: 50,
      paddingLeft: 200,
      paddingRight: 200,
      backgroundColor: "background-main-2"
    });

    this.buildLayout();
  },

  members: {
    buildLayout: function() {
      const socialNetworksLayout = this.__createSocialNetworks();
      this._add(socialNetworksLayout);

      this._add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      const memberOfLayout = this.__createMemberOf();
      this._add(memberOfLayout);
    },

    __createSocialNetworks: function() {
      const socialNetworksLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));

      const createSociaNetworkIcon = (image, link) => {
        const sociaNetworkIcon = new qx.ui.basic.Image(image).set({
          alignY: "middle",
          cursor: "pointer"
        });
        sociaNetworkIcon.addListener("tap", () => window.open(link, "_blank"));
        return sociaNetworkIcon;
      };
      [{
        image: "@FontAwesome5Solid/facebook/28",
        link: "https://www.facebook.com/itisfoundation/"
      }, {
        image: "@FontAwesome5Solid/youtube/28",
        link: "https://www.youtube.com/@zurichmedtechag2809"
      }, {
        image: "@FontAwesome5Solid/linked/28",
        link: "https://ch.linkedin.com/company/itis-foundation"
      }].forEach(template => socialNetworksLayout.add(createSociaNetworkIcon(template.image, template.link)));

      return socialNetworksLayout;
    },

    __createMemberOf: function() {
      const socialNetworksLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignY: "middle"
      }));
      const label = new qx.ui.basic.Label("Member of:").set({
        font: "text-16",
        alignY: "middle"
      });
      socialNetworksLayout.add(label);

      const image = new qx.ui.basic.Image("https://www.z43.swiss/z43_logo_white.svg").set({
        width: 100,
        height: 100,
        cursor: "pointer",
        scale: true
      });
      image.addListener("tap", () => window.open("https://www.z43.swiss/", "_blank"));
      socialNetworksLayout.add(image);

      return socialNetworksLayout;
    }
  }
});
