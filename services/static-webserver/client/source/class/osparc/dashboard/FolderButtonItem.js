/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget used for displaying Folder in the Study Browser
 *
 */

qx.Class.define("osparc.dashboard.FolderButtonItem", {
  extend: qx.ui.form.ToggleButton,
  implement: [qx.ui.form.IModel, osparc.filter.IFilterable],
  include: [qx.ui.form.MModelProperty, osparc.filter.MFilterable],

  construct: function(folderData) {
    this.base(arguments);

    this.set({
      appearance: "pb-study",
      width: osparc.dashboard.GridButtonBase.ITEM_WIDTH,
      minHeight: osparc.dashboard.ListButtonBase.ITEM_HEIGHT
    });

    const layout = new qx.ui.layout.Grid();
    layout.setSpacing(5);
    layout.setColumnFlex(this.self().POS.TITLE.column, 1);
    this._setLayout(layout);

    [
      "pointerover",
      "focus"
    ].forEach(e => this.addListener(e, this.__onPointerOver, this));

    [
      "pointerout",
      "focusout"
    ].forEach(e => this.addListener(e, this.__onPointerOut, this));

    this.addListener("changeValue", this.__itemSelected, this);

    this.setPriority(osparc.dashboard.CardBase.CARD_PRIORITY.ITEM);

    this.set({
      folderData
    });
  },

  properties: {
    cardKey: {
      check: "String",
      nullable: true
    },

    folderData: {
      check: "Object",
      nullable: false,
      init: null,
      apply: "__applyFolderData"
    },

    resourceType: {
      check: ["folder"],
      init: "folder",
      nullable: false
    },

    folderId: {
      check: "Number",
      nullable: false
    },

    title: {
      check: "String",
      nullable: true,
      apply: "__applyTitle"
    },

    description: {
      check: "String",
      nullable: true,
      apply: "__applyDescription"
    },

    accessRights: {
      check: "Object",
      nullable: true,
      apply: "__applyAccessRights"
    },

    sharedAccessRights: {
      check: "Object",
      nullable: true,
      apply: "__applySharedAccessRights"
    },

    lastModified: {
      check: "Date",
      nullable: true,
      apply: "__applyLastModified"
    },

    priority: {
      check: "Number",
      init: null,
      nullable: false
    }
  },

  statics: {
    POS: {
      ICON: {
        column: 0,
        row: 0,
        rowSpan: 2
      },
      TITLE: {
        column: 1,
        row: 0
      },
      DESCRIPTION: {
        column: 1,
        row: 0
      },
      SHARED: {
        column: 2,
        row: 0,
        rowSpan: 2
      },
      LAST_CHANGE: {
        column: 3,
        row: 0,
        rowSpan: 2
      },
      MENU: {
        column: 4,
        row: 0,
        rowSpan: 2
      }
    }
  },

  members: { // eslint-disable-line qx-rules/no-refs-in-members
    // overridden
    _forwardStates: {
      focused : true,
      hovered : true,
      selected : true,
      dragover : true
    },

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon": {
          control = new osparc.ui.basic.Thumbnail("@FontAwesome5Solid/folder/24", 32, 32).set({
            minHeight: 32,
            minWidth: 32
          });
          control.getChildControl("image").set({
            anonymous: true
          });
          this._add(control, this.self().POS.ICON);
          break;
        }
        case "title":
          control = new qx.ui.basic.Label().set({
            textColor: "contrasted-text-light",
            font: "text-14",
            alignY: "middle",
            allowGrowX: true,
            rich: true,
          });
          this._add(control, this.self().POS.TITLE);
          break;
        case "description":
          control = new qx.ui.basic.Label().set({
            textColor: "contrasted-text-dark",
            font: "text-12",
            alignY: "middle",
            allowGrowX: true,
            rich: true
          });
          this._add(control, this.self().POS.DESCRIPTION);
          break;
        case "shared-icon":
          control = new qx.ui.basic.Image().set({
            minWidth: 30,
            alignY: "middle"
          });
          this._add(control, this.self().POS.SHARED);
          break;
        case "last-modified":
          control = new qx.ui.basic.Label().set({
            anonymous: true,
            font: "text-12",
            allowGrowY: false,
            minWidth: 100,
            alignY: "middle"
          });
          this._add(control, this.self().POS.SHARED);
          break;
        case "menu-button": {
          control = new qx.ui.form.MenuButton().set({
            appearance: "form-button-outlined",
            padding: [0, 8],
            maxWidth: osparc.dashboard.ListButtonBase.MENU_BTN_DIMENSIONS,
            maxHeight: osparc.dashboard.ListButtonBase.MENU_BTN_DIMENSIONS,
            icon: "@FontAwesome5Solid/ellipsis-v/14",
            focusable: false
          });
          // make it circular
          control.getContentElement().setStyles({
            "border-radius": `${osparc.dashboard.ListButtonBase.MENU_BTN_DIMENSIONS / 2}px`
          });
          this._add(control, this.self().POS.MENU);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __applyFolderData: function(folderData) {
      console.log("folderData", folderData);
      this.getChildControl("icon");
      this.set({
        cardKey: "folder-" + folderData.id,
        folderId: folderData.id,
        title: folderData.name,
        description: folderData.description,
        accessRights: folderData.accessRights,
        lastModified: new Date(folderData.lastModified),
        sharedAccessRights: folderData.sharedAccessRights,
      });
    },

    __applyTitle: function(value) {
      const label = this.getChildControl("title");
      label.setValue(value);
    },

    __applyDescription: function(value) {
      const label = this.getChildControl("description");
      label.setValue(value);
    },

    __applyLastModified: function(value) {
      if (value) {
        const label = this.getChildControl("last-modified");
        label.setValue(osparc.utils.Utils.formatDateAndTime(value));
      }
    },

    __applyAccessRights: function(value) {
      if (value && value["delete"]) {
        const menuButton = this.getChildControl("menu-button");
        menuButton.setVisibility("visible");

        const menu = new qx.ui.menu.Menu().set({
          position: "bottom-right"
        });
        menuButton.setMenu(menu);
      }
    },

    __applySharedAccessRights: function(value) {
      if (value && Object.keys(value).length) {
        const shareIcon = this.getChildControl("shared-icon");
        shareIcon.addListener("tap", e => e.stopPropagation());
        shareIcon.addListener("pointerdown", e => e.stopPropagation());
        osparc.dashboard.CardBase.populateShareIcon(shareIcon, value);
      }
    },

    __itemSelected: function() {
      this.setValue(false);

      console.log("folder tapped", this.getFolderId());
    },

    __onPointerOver: function() {
      this.addState("hovered");
    },

    __onPointerOut : function() {
      this.removeState("hovered");
    },

    _filter: function() {
      this.exclude();
    },

    _unfilter: function() {
      this.show();
    },

    _shouldApplyFilter: function(data) {
      console.log("_shouldApplyFilter", data);
      return false;
    },

    _shouldReactToFilter: function(data) {
      console.log("_shouldReactToFilter", data);
      return false;
    }
  },

  destruct: function() {
    this.removeListener("pointerover", this.__onPointerOver, this);
    this.removeListener("pointerout", this.__onPointerOut, this);
  }
});
