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
  },

  members: {
    _applyFetching: function(value) {
      const title = this.getChildControl("title");
      const desc = this.getChildControl("subtitle-text");
      if (value) {
        title.setValue(this.tr("Loading..."));
        desc.setValue("");
        this.setIcon(osparc.dashboard.CardBase.LOADING_ICON);
        this.getChildControl("icon").getChildControl("image").getContentElement()
          .addClass("rotate");
      } else {
        title.setValue(this.tr("Load More"));
        desc.setValue(this.tr("Click to load more").toString());
        this.setIcon("@FontAwesome5Solid/paw/");
        this.getChildControl("icon").getChildControl("image").getContentElement()
          .removeClass("rotate");
      }
      this.setEnabled(!value);
    },

    _onToggleChange: function(e) {
      this.setValue(false);
    },

    _shouldApplyFilter: function() {
      return false;
    },

    _shouldReactToFilter: function() {
      return false;
    }
  }
});
