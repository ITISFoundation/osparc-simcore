/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.dashboard.GroupHeader", {
  extend: osparc.dashboard.ListButtonBase,

  construct: function() {
    this.base(arguments);

    this.set({
      cursor: "default",
      backgroundColor: "transparent"
    });
    this.GroupHeader = true;
  },

  members: {
    buildLayout: function(titleText) {
      const title = this.getChildControl("title");
      if (titleText) {
        title.setValue(titleText);
      }
      this.setIcon("@FontAwesome5Solid/tags/12");

      this._getChildren().forEach(item => {
        item.setOpacity(0.8);
      });
    },

    isLocked: function() {
      return true;
    },

    _onToggleChange: function() {
      this.setValue(false);
    },

    _shouldApplyFilter: function(data) {
      if (data.text) {
        const checks = [
          this.getChildControl("title").getValue().toString()
        ];
        if (checks.filter(label => label.toLowerCase().trim().includes(data.text)).length == 0) {
          return true;
        }
      }
      return false;
    }
  }
});
