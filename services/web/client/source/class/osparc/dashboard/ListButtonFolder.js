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

    __applyId: function(value) {
      const tags = osparc.store.Store.getInstance().getTags();
      const foundTag = tags.find(tag => tag.id === value);
      if (foundTag) {
        this.setTitle(foundTag.name);

        const description = this.getChildControl("description");
        description.setValue(foundTag.description);

        const icon = this.getChildControl("icon").getChildControl("image");
        icon.setTextColor(foundTag.color);
      }
    },

    // overridden
    _applyLastChangeDate: function(value, old) {
      if (value) {
        const label = this.getChildControl("last-change");
        label.setValue(osparc.utils.Utils.formatDateAndTime(value));
      }
    },

    _onToggleChange: function(e) {
      this.setValue(false);
    },

    __filterText: function(text) {
      const checks = [
        this.getTitle()
      ];
      return osparc.dashboard.CardBase.filterText(checks, text);
    },

    _shouldApplyFilter: function(data) {
      const filterData = data["searchBarFilter-study"];
      if (this.__filterText(filterData.text)) {
        return true;
      }
      if (filterData.tags && filterData.tags.length) {
        return true;
      }
      if (filterData.classifiers && filterData.classifiers.length) {
        return true;
      }
      return false;
    },

    _shouldReactToFilter: function(data) {
      const filterData = data["searchBarFilter-study"];
      if (filterData.text && filterData.text.length > 1) {
        return true;
      }
      if (filterData.tags && filterData.tags.length) {
        return true;
      }
      if (filterData.classifiers && filterData.classifiers.length) {
        return true;
      }
      return false;
    }
  }
});
