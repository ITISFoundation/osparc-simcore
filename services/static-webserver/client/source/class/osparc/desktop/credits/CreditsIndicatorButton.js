/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.desktop.credits.CreditsIndicatorButton", {
  extend: osparc.desktop.credits.CreditsImage,

  construct: function() {
    this.base(arguments);

    this.set({
      cursor: "pointer",
      padding: [3, 8]
    });

    this.getChildControl("image").set({
      width: 24,
      height: 24
    });

    this.__creditsContainer = new osparc.desktop.credits.CreditsNavBarContainer();
    this.__creditsContainer.exclude();

    this.addListener("tap", this.__buttonTapped, this);
  },


  members: {
    __creditsContainer: null,
    __tappedOut: null,

    __buttonTapped: function() {
      if (this.__tappedOut) {
        this.__tappedOut = false;
        return;
      }
      this.__showCreditsContainer();
    },

    __showCreditsContainer: function() {
      const tapListener = event => {
        // In case a notification was tapped propagate the event so it can be handled by the NotificationUI
        if (osparc.utils.Utils.isMouseOnElement(this.__creditsContainer, event)) {
          return;
        }
        // I somehow can't stop the propagation of the event so workaround:
        // If the user tapped on the bell we don't want to show it again
        if (osparc.utils.Utils.isMouseOnElement(this, event)) {
          this.__tappedOut = true;
        }
        this.__hideNotifications();
        document.removeEventListener("mousedown", tapListener, this);
      };

      const bounds = this.getBounds();
      const cel = this.getContentElement();
      if (cel) {
        const domeEle = cel.getDomElement();
        if (domeEle) {
          const rect = domeEle.getBoundingClientRect();
          bounds.left = parseInt(rect.x);
          bounds.top = parseInt(rect.y);
        }
      }
      const bottom = bounds.top+bounds.height;
      const right = bounds.left+bounds.width;
      this.__creditsContainer.setPosition(right, bottom);
      this.__creditsContainer.show();

      document.addEventListener("mousedown", tapListener, this);
    },

    __hideNotifications: function() {
      this.__creditsContainer.exclude();
    }
  }
});
