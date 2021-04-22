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

qx.Class.define("osparc.dashboard.StudyBrowserButtonLoadMore", {
  extend: osparc.dashboard.StudyBrowserButtonBase,

  construct: function() {
    this.base(arguments);

    this.__applyFetching(false);
  },

  properties: {
    fetching: {
      check: "Boolean",
      init: false,
      nullable: false,
      apply: "__applyFetching"
    }
  },

  members: {
    checkIsOnScreen: function() {
      const isInViewport = element => {
        const rect = element.getBoundingClientRect();
        const html = document.documentElement;
        return (
          rect.top >= 0 &&
          rect.left >= 0 &&
          rect.bottom <= (window.innerHeight || html.clientHeight) &&
          rect.right <= (window.innerWidth || html.clientWidth)
        );
      };

      const checkIsOnScreen = isInViewport(this.getContentElement().getDomElement());
      return checkIsOnScreen;
    },

    __applyFetching: function(value) {
      const title = this.getChildControl("title");
      const desc = this.getChildControl("subtitle-text");
      if (value) {
        title.setValue(this.tr("Loading studies..."));
        desc.setValue("");
        this.setIcon("@FontAwesome5Solid/circle-notch/60");
        this.getChildControl("icon").getChildControl("image").getContentElement()
          .addClass("rotate");
      } else {
        title.setValue(this.tr("Load More"));
        desc.setValue(this.tr("Click to load more").toString());
        this.setIcon("@FontAwesome5Solid/paw/60");
        this.getChildControl("icon").getChildControl("image").getContentElement()
          .removeClass("rotate");
      }
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
