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
  extend: qx.ui.form.Button,

  construct: function() {
    this.base(arguments);

    this.set({
      backgroundColor: "transparent"
    });

    const store = osparc.store.Store.getInstance();
    store.bind("contextWallet", this, "wallet");

    this.__creditsContainer = new osparc.desktop.credits.CreditsNavBarContainer();
    this.__creditsContainer.exclude();

    this.addListener("tap", this.__buttonTapped, this);
  },

  properties: {
    wallet: {
      check: "osparc.data.model.Wallet",
      init: null,
      nullable: true,
      event: "changeWallet",
      apply: "__applyWallet"
    }
  },

  members: {
    __creditsContainer: null,
    __tappedOut: null,

    __applyWallet: function() {
      osparc.desktop.credits.Utils.setCreditsIconToButton(this);
    },

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
      this.__creditsContainer.setPosition(bounds.left+bounds.width-2, bounds.top+bounds.height-2);
      this.__creditsContainer.show();

      document.addEventListener("mousedown", tapListener, this);
    },

    __hideNotifications: function() {
      this.__creditsContainer.exclude();
    }
  }
});
