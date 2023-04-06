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
      padding: 30,
      paddingLeft: 250,
      paddingRight: 250,
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
      const socialNetworksLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(20));

      const createSociaNetworkIcon = (image, link) => {
        const sociaNetworkIcon = new qx.ui.basic.Image(image).set({
          maxWidth: 28,
          maxHeight: 28,
          scale: true,
          alignY: "middle",
          cursor: "pointer"
        });
        sociaNetworkIcon.addListener("tap", () => window.open(link, "_blank"));
        return sociaNetworkIcon;
      };
      [{
        image: "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b8/2021_Facebook_icon.svg/2048px-2021_Facebook_icon.svg.png",
        link: "https://www.facebook.com/itisfoundation/"
      }, {
        image: "https://upload.wikimedia.org/wikipedia/commons/thumb/0/09/YouTube_full-color_icon_%282017%29.svg/2560px-YouTube_full-color_icon_%282017%29.svg.png",
        link: "https://www.youtube.com/@zurichmedtechag2809"
      }, {
        image: "https://upload.wikimedia.org/wikipedia/commons/thumb/8/81/LinkedIn_icon.svg/2048px-LinkedIn_icon.svg.png",
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
