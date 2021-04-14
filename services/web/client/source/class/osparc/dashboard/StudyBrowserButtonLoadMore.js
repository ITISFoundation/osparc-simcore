/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Tobias Oetiker (oetiker)

************************************************************************ */

/* eslint "qx-rules/no-refs-in-members": "warn" */

/**
 * Widget used mainly by StudyBrowser for displaying Studies
 *
 * It consists of a thumbnail and creator and last change as caption
 */

qx.Class.define("osparc.dashboard.StudyBrowserButtonLoadMore", {
  extend: osparc.dashboard.StudyBrowserButtonBase,

  construct: function() {
    this.base(arguments);

    this.__applyFetching(false);
  },

  properties: {
    nStudies: {
      check: "Number",
      init: 0,
      nullable: false
    },

    fetching: {
      check: "Boolean",
      init: false,
      nullable: false,
      apply: "__applyFetching"
    }
  },

  members: {
    __applyFetching: function(value) {
      const title = this.getChildControl("title");
      const desc = this.getChildControl("subtitle-text");
      if (value) {
        title.setValue(this.tr("Loading"));
        desc.setValue("");
        this.setIcon("@FontAwesome5Solid/crow/60");
      } else {
        title.setValue(this.tr("Load More"));
        desc.setValue(this.tr("Click to load more").toString());
        this.setIcon("@FontAwesome5Solid/paw/60");
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
