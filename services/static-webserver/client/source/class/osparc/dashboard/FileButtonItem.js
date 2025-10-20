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
  extend: osparc.dashboard.ListButtonBase,

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
      file: file
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
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "date-by":
          control = new osparc.ui.basic.DateAndBy();
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.LAST_CHANGE
          });
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
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.OPTIONS
          });
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __applyFile: function(file) {
      const id = file.getPath();
      this.set({
        cardKey: "file-" + id,
      });
      osparc.utils.Utils.setIdToWidget(this, "fileItem_" + id);

      const icon = this.getChildControl("icon");
      if (file.getIsDirectory()) {
        icon.setSource("@FontAwesome5Solid/folder/24");
      } else {
        icon.setSource("@FontAwesome5Solid/file/24");
      }

      const label = this.getChildControl("title");
      label.set({
        value: file.getName(),
        toolTipText: file.getName(),
      });

      const dateBy = this.getChildControl("date-by");
      dateBy.set({
        date: file.getModifiedAt(),
        toolTipText: this.tr("Last modified"),
      });

      const menuButton = this.getChildControl("menu-button");
      menuButton.setVisibility("visible");

      const menu = new qx.ui.menu.Menu().set({
        appearance: "menu-wider",
        position: "bottom-right",
      });

      const openLocationButton = new qx.ui.menu.Button(this.tr("Open location"), "@FontAwesome5Solid/folder/12");
      openLocationButton.addListener("execute", () => this.fireDataEvent("openLocation", {
        projectId: file.getProjectId(),
        path: file.getPath()
      }), this);
      menu.add(openLocationButton);

      menuButton.setMenu(menu);
    },
  }
});
