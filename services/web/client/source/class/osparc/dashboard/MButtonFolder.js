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

qx.Mixin.define("osparc.dashboard.MButtonFolder", {
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

    _onToggleChange: function(e) {
      this.setValue(false);
    },

    __filterText: function(text) {
      const checks = [
        this.getTitle()
      ];
      return osparc.dashboard.CardBase.filterText(checks, text);
    },

    __filterFolder: function(folderId) {
      // do not show if folder is selected
      return folderId !== null;
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
      if (this.__filterFolder(filterData.folder)) {
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
      if (filterData.folder) {
        return true;
      }
      return false;
    }
  }
});
