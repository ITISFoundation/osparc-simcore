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

qx.Class.define("osparc.dashboard.StudyBrowserButtonNew", {
  extend: osparc.dashboard.StudyBrowserButtonBase,

  construct: function() {
    this.base(arguments);

    this.__buildLayout();
  },

  members: {
    __buildLayout: function() {
      const title = this.getChildControl("title");
      title.setValue(this.tr("Empty Study"));

      const desc = this.getChildControl("subtitle-text");
      desc.setValue(this.tr("Start with a empty study").toString());

      this.setIcon("@FontAwesome5Solid/plus/60");
    },

    _onToggleChange: function(e) {
      this.setValue(false);
    },

    _shouldApplyFilter: function(data) {
      if (data.text) {
        const checks = [
          this.getChildControl("title").getValue().toString(),
          this.getChildControl("subtitle-text").getValue().toString()
        ];
        if (checks.filter(label => label.toLowerCase().trim().includes(data.text)).length == 0) {
          return true;
        }
      }
      return false;
    }
  }
});
