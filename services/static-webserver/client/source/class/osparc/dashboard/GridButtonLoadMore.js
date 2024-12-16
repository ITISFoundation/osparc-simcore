/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Study card to show that more studies are being fetched
 */

qx.Class.define("osparc.dashboard.GridButtonLoadMore", {
  extend: osparc.dashboard.GridButtonBase,

  construct: function() {
    this.base(arguments);

    this.setPriority(osparc.dashboard.CardBase.CARD_PRIORITY.LOADER);

    this._applyFetching(false);

    // A minimalistic spinning wheel
    this.getChildControl("header").exclude();
    this.getChildControl("footer").exclude();
    this.set({
      backgroundColor: "transparent"
    });
  },

  members: {
    _applyFetching: function(value) {
      this.setIcon(osparc.dashboard.CardBase.LOADING_ICON);
      if (value) {
        this.getChildControl("icon").getChildControl("image").getContentElement()
          .addClass("rotate");
      } else {
        this.getChildControl("icon").getChildControl("image").getContentElement()
          .removeClass("rotate");
      }
      this.setEnabled(!value);
    },

    _shouldApplyFilter: function() {
      return false;
    },

    _shouldReactToFilter: function() {
      return false;
    }
  }
});
