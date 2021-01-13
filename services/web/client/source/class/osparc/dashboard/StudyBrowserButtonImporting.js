/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Tobias Oetiker (oetiker)

************************************************************************ */

qx.Class.define("osparc.dashboard.StudyBrowserButtonImporting", {
  extend: osparc.dashboard.StudyBrowserButtonBase,

  construct: function() {
    this.base(arguments);

    this.__buildLayout();
  },

  members: {
    __buildLayout: function() {
      const title = this.getChildControl("title");
      title.setValue(this.tr("Importing Study..."));

      this.setIcon("@FontAwesome5Solid/file-import/60");

      this.set({
        cursor: "not-allowed"
      });

      this._getChildren().forEach(item => {
        item.setOpacity(0.4);
      });
    },

    isLocked: function() {
      return true;
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
      if (data.tags && data.tags.length) {
        return true;
      }
      if (data.classifiers && data.classifiers.length) {
        return true;
      }
      return false;
    }
  }
});
