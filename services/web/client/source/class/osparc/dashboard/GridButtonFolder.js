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

qx.Class.define("osparc.dashboard.GridButtonFolder", {
  extend: osparc.dashboard.GridButtonBase,

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

  statics: {
    ICON_SIZE: 80
  },

  members: {
    __buildLayout: function() {
      const title = this.getChildControl("title");
      title.setValue(this.tr("Folder"));

      this.setIcon(osparc.dashboard.CardBase.FOLDER_ICON);
    },

    __applyId: function(value) {
      const folders = osparc.store.Store.getInstance().getFolders();
      const foundFolder = folders.find(folder => folder.id === value);
      if (foundFolder) {
        this.setTitle(foundFolder.name);

        const description = this.getChildControl("subtitle-text");
        description.setValue(foundFolder.description);

        const icon = this.getChildControl("icon").getChildControl("image");
        icon.setTextColor(foundFolder.color);
      }
    },

    // overridden
    _applyIcon: function(value) {
      this.base(arguments, value);

      const image = this.getChildControl("icon").getChildControl("image");
      let imgSrc = image.getSource();
      imgSrc = imgSrc.replace("/"+osparc.dashboard.GridButtonBase.ICON_SIZE, "/"+this.self().ICON_SIZE);
      image.setSource(imgSrc);
    },

    // overridden
    _applyLastChangeDate: function(value, old) {
      if (value) {
        const label = this.getChildControl("subtitle-text");
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

    __filterFolder: function(folderId) {
      return this.getId() !== folderId;
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
