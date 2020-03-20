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

qx.Class.define("osparc.dashboard.StudyBrowserListNew", {
  extend: osparc.dashboard.StudyBrowserListBase,

  construct: function() {
    this.base(arguments);

    this.__buildLayout();
  },

  members: {
    __buildLayout: function() {
      const title = this.getChildControl("title");
      title.setValue(this.tr("Create New Study"));

      const desc1 = this.getChildControl("desc1");
      desc1.setValue(this.tr("Start with a empty study"));

      this.setIcon("@FontAwesome5Solid/plus-circle/64");
    },

    _onToggleChange: function(e) {
      this.setValue(false);
    },

    _shouldApplyFilter: function(data) {
      if (data.text) {
        return true;
      }
      if (data.tags && data.tags.length) {
        return true;
      }
      return false;
    }
  }
});
