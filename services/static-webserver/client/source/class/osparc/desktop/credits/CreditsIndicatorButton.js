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

    osparc.utils.Utils.setIdToWidget(this, "creditsIndicatorButton");

    this.set({
      cursor: "pointer",
      padding: [3, 8]
    });

    this.getChildControl("image").set({
      width: 24,
      height: 24
    });

    this.addListener("tap", this.__buttonTapped, this);
  },

  members: {
    __creditsContainer: null,
    __tapListener: null,

    __buttonTapped: function() {
      if (this.__creditsContainer && this.__creditsContainer.isVisible()) {
        this.__hideCreditsContainer();
      } else {
        this.__showCreditsContainer();
      }
    },

    __showCreditsContainer: function() {
      if (!this.__creditsContainer) {
        this.__creditsContainer = new osparc.desktop.credits.CreditsSummary();
        this.__creditsContainer.exclude();
      }

      this.__positionCreditsContainer();

      // Show the container
      this.__creditsContainer.show();

      // Add listeners for taps outside the container to hide it
      document.addEventListener("mousedown", this.__onTapOutsideMouse.bind(this), true);
    },

    __positionCreditsContainer: function() {
      const bounds = osparc.utils.Utils.getBounds(this);
      const bottom = bounds.top + bounds.height;
      const right = bounds.left + bounds.width;
      this.__creditsContainer.setPosition(right, bottom);
    },

    __onTapOutsideMouse: function(event) {
      this.__handleOutsideEvent(event);
    },

    __handleOutsideEvent: function(event) {
      const offset = 0;
      const onContainer = osparc.utils.Utils.isMouseOnElement(this.__creditsContainer, event, offset);
      const onButton = osparc.utils.Utils.isMouseOnElement(this, event, offset);
      if (!onContainer && !onButton) {
        this.__hideCreditsContainer();
      }
    },

    __hideCreditsContainer: function() {
      if (this.__creditsContainer) {
        this.__creditsContainer.exclude();
      }

      // Remove listeners for outside clicks/taps
      document.removeEventListener("mousedown", this.__onTapOutsideMouse.bind(this), true);
    }
  }
});
