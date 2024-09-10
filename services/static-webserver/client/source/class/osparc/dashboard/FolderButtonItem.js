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

  /**
    * @param folder {osparc.data.model.Folder}
    */
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

  events: {
    "folderSelected": "qx.event.type.Data",
    "folderUpdated": "qx.event.type.Data",
    "moveFolderToFolderRequested": "qx.event.type.Data",
    "moveFolderToWorkspaceRequested": "qx.event.type.Data",
    "deleteFolderRequested": "qx.event.type.Data"
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

    parentFolderId: {
      check: "Number",
      nullable: true,
      init: true
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
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon": {
          control = new qx.ui.basic.Image().set({
            source: "@FontAwesome5Solid/folder/26",
            anonymous: true,
            height: 40,
            padding: 5
          });
          this._add(control, osparc.dashboard.FolderButtonBase.POS.ICON);
          break;
        }
        case "title":
          control = new qx.ui.basic.Label().set({
            anonymous: true,
            font: "text-14",
            rich: true,
          });
          this._add(control, osparc.dashboard.FolderButtonBase.POS.TITLE);
          break;
        case "last-modified":
          control = new qx.ui.basic.Label().set({
            anonymous: true,
            font: "text-12",
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
        cardKey: "folder-" + folder.getFolderId()
      });
      folder.bind("folderId", this, "folderId");
      folder.bind("parentId", this, "parentFolderId");
      folder.bind("name", this, "title");
      folder.bind("lastModified", this, "lastModified");

      this.__addMenuButton();
    },

    __applyTitle: function(value) {
      const label = this.getChildControl("title");
      label.setValue(value);
    },

    __applyLastModified: function(value) {
      if (value) {
        const label = this.getChildControl("last-modified");
        label.setValue(osparc.utils.Utils.formatDateAndTime(value));
      }
    },

    __addMenuButton: function() {
      const menuButton = this.getChildControl("menu-button");
      menuButton.setVisibility("visible");

      const menu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });

      const editButton = new qx.ui.menu.Button(this.tr("Rename..."), "@FontAwesome5Solid/pencil-alt/12");
      editButton.addListener("execute", () => this.__editFolder(), this);
      menu.add(editButton);

      const moveToFolderButton = new qx.ui.menu.Button(this.tr("Move to Folder..."), "@FontAwesome5Solid/folder/12");
      moveToFolderButton.addListener("execute", () => this.fireDataEvent("moveFolderToFolderRequested", this.getFolderId()), this);
      menu.add(moveToFolderButton);

      const moveToWorkspaceButton = new qx.ui.menu.Button(this.tr("Move to Workspace..."), "");
      moveToWorkspaceButton.addListener("execute", () => this.fireDataEvent("moveFolderToWorkspaceRequested", this.getFolderId()), this);
      menu.add(moveToWorkspaceButton);

      menu.addSeparator();

      const deleteButton = new qx.ui.menu.Button(this.tr("Delete"), "@FontAwesome5Solid/trash/12");
      deleteButton.addListener("execute", () => this.__deleteStudyRequested(), this);
      menu.add(deleteButton);

      menuButton.setMenu(menu);
    },

    __itemSelected: function(newVal) {
      if (newVal) {
        this.fireDataEvent("folderSelected", this.getFolderId());
      }
      this.setValue(false);
    },

    __editFolder: function() {
      const folder = this.getFolder();
      const newFolder = false;
      const folderEditor = new osparc.editor.FolderEditor(newFolder).set({
        label: folder.getName(),
      });
      const title = this.tr("Edit Folder");
      const win = osparc.ui.window.Window.popUpInWindow(folderEditor, title, 300, 150);
      folderEditor.addListener("updateFolder", () => {
        const newName = folderEditor.getLabel();
        const updateData = {
          "name": newName,
        };
        osparc.data.model.Folder.putFolder(this.getFolderId(), updateData)
          .then(() => {
            folder.set({
              name: newName,
            });
            this.fireDataEvent("folderUpdated", folder.getFolderId());
          })
          .catch(err => console.error(err));
        win.close();
      });
      folderEditor.addListener("cancel", () => win.close());
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
          this.fireDataEvent("deleteFolderRequested", this.getFolderId());
        }
      }, this);
    }
  }
});
