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
 * Widget used for displaying a Folder in the Study Browser
 *
 */

qx.Class.define("osparc.dashboard.FolderButtonItem", {
  extend: osparc.dashboard.FolderButtonBase,

  construct: function(folder) {
    this.base(arguments);

    this.set({
      appearance: "pb-study"
    });

    this.addListener("changeValue", e => this.__itemSelected(e.getData()), this);

    this.setPriority(osparc.dashboard.CardBase.CARD_PRIORITY.ITEM);

    this.set({
      folder: folder
    });
  },

  properties: {
    folder: {
      check: "osparc.data.model.Folder",
      nullable: false,
      init: null,
      apply: "__applyFolder"
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
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon": {
          control = new osparc.dashboard.FolderWithSharedIcon().set({
            anonymous: true,
            alignY: "middle",
            alignX: "center",
            padding: 5
          });
          this._add(control, osparc.dashboard.FolderButtonBase.POS.ICON);
          break;
        }
        case "title":
          control = new qx.ui.basic.Label().set({
            anonymous: true,
            font: "text-14",
            alignY: "middle",
            allowGrowX: true,
            rich: true,
          });
          this._add(control, osparc.dashboard.FolderButtonBase.POS.TITLE);
          break;
        case "last-modified":
          control = new qx.ui.basic.Label().set({
            anonymous: true,
            font: "text-12",
            allowGrowY: false,
            minWidth: 100,
            alignY: "middle"
          });
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
          this._add(control, osparc.dashboard.FolderButtonBase.POS.MENU);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __applyFolder: function(folder) {
      this.getChildControl("icon");
      this.set({
        cardKey: "folder-" + folder.getId()
      });
      folder.bind("id", this, "folderId");
      folder.bind("name", this, "title");
      folder.bind("description", this, "description");
      folder.bind("sharedAccessRights", this, "sharedAccessRights");
      folder.bind("lastModified", this, "lastModified");
      folder.bind("accessRights", this, "accessRights");
    },

    __applyTitle: function(value) {
      const label = this.getChildControl("title");
      label.setValue(value);
      this.__updateTooltip();
    },

    __applyDescription: function() {
      this.__updateTooltip();
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

        const renameButton = new qx.ui.menu.Button(this.tr("Rename..."));
        renameButton.addListener("execute", () => {
          const renamer = new osparc.widget.Renamer(this.getTitle());
          renamer.addListener("labelChanged", e => {
            renamer.close();
            const newLabel = e.getData()["newLabel"];
            osparc.data.model.Folder.patchFolder(this.getFolderId(), "name", newLabel)
              .then(() => this.getFolder().setName(newLabel))
              .catch(err => console.error(err));
          }, this);
          renamer.center();
          renamer.open();
        });
        menu.add(renameButton);

        const shareButton = new qx.ui.menu.Button(this.tr("Share..."));
        shareButton.addListener("execute", () => this.__openShareWith(), this);
        menu.add(shareButton);

        menu.addSeparator();

        const deleteButton = new qx.ui.menu.Button(this.tr("Delete"));
        deleteButton.addListener("execute", () => this.__deleteStudyRequested(), this);
        menu.add(deleteButton);

        menuButton.setMenu(menu);
      }
    },

    __applySharedAccessRights: function(value) {
      if (value && Object.keys(value).length) {
        const shareIcon = this.getChildControl("icon").getChildControl("shared-icon");
        osparc.dashboard.CardBase.populateShareIcon(shareIcon, value);
      }
    },

    __updateTooltip: function() {
      const toolTipText = this.getTitle() + (this.getDescription() ? "<br>" + this.getDescription() : null);
      this.set({
        toolTipText
      })
    },

    __itemSelected: function(newVal) {
      if (newVal) {
        console.log("folder tapped", this.getFolderId());
      }
      this.setValue(false);
    },

    __openShareWith: function() {
      console.log("Open share with", this.getTitle());
    },

    __deleteStudyRequested: function() {
      const msg = this.tr("Are you sure you want to delete") + " <b>" + this.getTitle() + "</b>?";
      const confirmationWin = new osparc.ui.window.Confirmation(msg).set({
        confirmText: this.tr("Delete"),
        confirmAction: "delete"
      });
      confirmationWin.center();
      confirmationWin.open();
      confirmationWin.addListener("close", () => {
        if (confirmationWin.getConfirmed()) {
          console.log("Delete", this.getTitle());
        }
      }, this);
    }
  }
});
