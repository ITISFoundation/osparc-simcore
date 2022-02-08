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

qx.Class.define("osparc.dashboard.ListButtonFolder", {
  extend: osparc.dashboard.ListButtonBase,

  construct: function() {
    this.base(arguments);

    this.__buildLayout();
  },

  properties: {
    id: {
      check: "Number",
      nullable: false,
      init: null,
      apply: "__applyId"
    }
  },

  members: {
    __buildLayout: function() {
      const title = this.getChildControl("title");
      title.setValue(this.tr("Folder"));

      this.setIcon(osparc.dashboard.CardBase.FOLDER_ICON);
    },

    __applyId: function() {
      const tags = osparc.store.Store.getInstance().getTags();
      console.log(tags);
    },

    _onToggleChange: function(e) {
      this.setValue(false);
    },

    _shouldApplyFilter: function(data) {
      return false;
    },

    _shouldReactToFilter: function(data) {
      return false;
    }
  }
});
