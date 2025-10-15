/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget used for displaying a File in the Study Browser
 *
 */

qx.Class.define("osparc.dashboard.FileButtonItem", {
  extend: osparc.dashboard.FolderButtonBase,

  /**
    * @param file {osparc.data.model.File} The file to display
    */
  construct: function(file) {
    this.base(arguments);

    this.set({
      appearance: "pb-study", // change this,
      cursor: "auto",
    });

    this.setPriority(osparc.dashboard.CardBase.CARD_PRIORITY.ITEM);

    this.set({
      folder: folder
    });
  },

  events: {
    "openLocation": "qx.event.type.Data",
  },

  properties: {
    file: {
      check: "osparc.data.model.File",
      nullable: false,
      init: null,
      apply: "__applyFile",
    },

    title: {
      check: "String",
      nullable: true,
      apply: "__applyTitle"
    },

    lastModified: {
      check: "Date",
      nullable: true,
      apply: "__applyLastModified"
    },
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon": {
          control = new osparc.dashboard.FolderWithSharedIcon().set({
            anonymous: true,
            height: 40,
            padding: 5
          });
          this._add(control, osparc.dashboard.FolderButtonBase.POS.ICON);
          break;
        }
        case "title":
          control = new qx.ui.basic.Label().set({
            font: "text-14",
          });
          this._add(control, osparc.dashboard.FolderButtonBase.POS.TITLE);
          break;
        case "date-by":
          control = new osparc.ui.basic.DateAndBy();
          this._add(control, osparc.dashboard.FolderButtonBase.POS.SUBTITLE);
          break;
        case "menu-button": {
          control = new qx.ui.form.MenuButton().set({
            appearance: "form-button-outlined",
            padding: [0, 8],
            maxWidth: osparc.dashboard.ListButtonItem.MENU_BTN_DIMENSIONS,
            maxHeight: osparc.dashboard.ListButtonItem.MENU_BTN_DIMENSIONS,
            icon: "@FontAwesome5Solid/ellipsis-v/14",
            focusable: false
          });
          // make it circular
          control.getContentElement().setStyles({
            "border-radius": `${osparc.dashboard.ListButtonItem.MENU_BTN_DIMENSIONS / 2}px`
          });
          osparc.utils.Utils.setIdToWidget(control, "folderItemMenuButton");
          this._add(control, osparc.dashboard.FolderButtonBase.POS.MENU);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __applyFile: function(file) {
      this.getChildControl("icon");
      this.set({
        cardKey: "file-" + file.getFileId()
      });
      file.bind("name", this, "title");
      file.bind("lastModified", this, "lastModified");

      osparc.utils.Utils.setIdToWidget(this, "fileItem_" + file.getFileId());

      this.__addMenuButton();
    },

    __applyTitle: function(value) {
      const label = this.getChildControl("title");
      label.set({
        value,
        toolTipText: value,
      });
    },

    __applyLastModified: function(value) {
      if (value) {
        const dateBy = this.getChildControl("date-by");
        dateBy.set({
          date: value,
          toolTipText: this.tr("Last modified"),
        })
      }
    },

    __addMenuButton: function() {
      const menuButton = this.getChildControl("menu-button");
      menuButton.setVisibility("visible");

      const menu = new qx.ui.menu.Menu().set({
        appearance: "menu-wider",
        position: "bottom-right",
      });

      const openLocationButton = new qx.ui.menu.Button(this.tr("Open location"), "@FontAwesome5Solid/folder/12");
      openLocationButton.addListener("execute", () => this.fireDataEvent("openLocation", this.getFolderId()), this);
      osparc.utils.Utils.setIdToWidget(openLocationButton, "openLocationMenuItem");
      menu.add(openLocationButton);

      menuButton.setMenu(menu);
    },
  }
});
