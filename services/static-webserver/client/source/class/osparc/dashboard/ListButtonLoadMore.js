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
 * Widget used mainly by StudyBrowser for displaying Studies
 *
 * It consists of a thumbnail and creator and last change as caption
 */

qx.Class.define("osparc.dashboard.ListButtonLoadMore", {
  extend: osparc.dashboard.ListButtonBase,

  construct: function() {
    this.base(arguments);

    this.setPriority(osparc.dashboard.CardBase.CARD_PRIORITY.LOADER);

    this._applyFetching(false);
  },

  members: {
    _applyFetching: function(value) {
      const title = this.getChildControl("title");
      if (value) {
        title.setValue(this.tr("Loading..."));
        this.setIcon(osparc.dashboard.CardBase.LOADING_ICON);
        this.getChildControl("icon").getChildControl("image").getContentElement()
          .addClass("rotate");
      } else {
        title.setValue(this.tr("Load More"));
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
