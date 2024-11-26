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
    "moveFolderToRequested": "qx.event.type.Data",
    "trashFolderRequested": "qx.event.type.Data",
    "untrashFolderRequested": "qx.event.type.Data",
    "deleteFolderRequested": "qx.event.type.Data",
    "changeContext": "qx.event.type.Data",
  },

  properties: {
    folder: {
      check: "osparc.data.model.Folder",
      nullable: false,
      init: null,
      apply: "__applyFolder"
    },

    workspaceId: {
      check: "Number",
      nullable: true,
      apply: "__applyWorkspaceId"
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
            anonymous: true,
            font: "text-14",
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
          osparc.utils.Utils.setIdToWidget(control, "folderItemMenuButton");
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
      folder.bind("workspaceId", this, "workspaceId");
      folder.bind("folderId", this, "folderId");
      folder.bind("parentFolderId", this, "parentFolderId");
      folder.bind("name", this, "title");
      folder.bind("lastModified", this, "lastModified");

      osparc.utils.Utils.setIdToWidget(this, "folderItem_" + folder.getFolderId());

      this.__addMenuButton();
    },

    __applyWorkspaceId: function(workspaceId) {
      const workspace = osparc.store.Workspaces.getInstance().getWorkspace(workspaceId);
      const accessRights = workspace ? workspace.getAccessRights() : {};
      if (accessRights && Object.keys(accessRights).length) {
        const shareIcon = this.getChildControl("icon").getChildControl("shared-icon");
        // if it's not shared don't show the share icon
        shareIcon.addListener("changeSource", e => {
          const newSource = e.getData();
          shareIcon.set({
            visibility: newSource.includes(osparc.dashboard.CardBase.SHARE_ICON) ? "hidden" : "visible"
          });
        });
        osparc.dashboard.CardBase.populateShareIcon(shareIcon, accessRights);
      }
    },

    __applyTitle: function(value) {
      const label = this.getChildControl("title");
      label.setValue(value);

      this.setToolTipText(value);
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

      const studyBrowserContext = osparc.store.Store.getInstance().getStudyBrowserContext();
      if (
        studyBrowserContext === "search" ||
        studyBrowserContext === "studiesAndFolders"
      ) {
        const editButton = new qx.ui.menu.Button(this.tr("Rename..."), "@FontAwesome5Solid/pencil-alt/12");
        editButton.addListener("execute", () => this.__editFolder(), this);
        menu.add(editButton);

        if (studyBrowserContext === "search") {
          const openLocationButton = new qx.ui.menu.Button(this.tr("Open location"), "@FontAwesome5Solid/external-link-alt/12");
          openLocationButton.addListener("execute", () => {
            const folder = this.getFolder();
            this.fireDataEvent("changeContext", {
              context: "studiesAndFolders",
              workspaceId: folder.getWorkspaceId(),
              folderId: folder.getParentFolderId(),
            });
          }, this);
          menu.add(openLocationButton);
        }

        const moveToButton = new qx.ui.menu.Button(this.tr("Move to..."), "@FontAwesome5Solid/folder/12");
        moveToButton.addListener("execute", () => this.fireDataEvent("moveFolderToRequested", this.getFolderId()), this);
        osparc.utils.Utils.setIdToWidget(moveToButton, "moveFolderMenuItem");
        menu.add(moveToButton);

        menu.addSeparator();

        const trashButton = new qx.ui.menu.Button(this.tr("Trash"), "@FontAwesome5Solid/trash/12");
        trashButton.addListener("execute", () => this.__trashFolderRequested(), this);
        menu.add(trashButton);
      } else if (studyBrowserContext === "trash") {
        const restoreButton = new qx.ui.menu.Button(this.tr("Restore"), "@MaterialIcons/restore_from_trash/16");
        restoreButton.addListener("execute", () => this.fireDataEvent("untrashFolderRequested", this.getFolder()), this);
        menu.add(restoreButton);

        menu.addSeparator();

        const deleteButton = new qx.ui.menu.Button(this.tr("Delete"), "@FontAwesome5Solid/trash/12");
        osparc.utils.Utils.setIdToWidget(deleteButton, "deleteFolderMenuItem");
        deleteButton.addListener("execute", () => this.__deleteFolderRequested(), this);
        menu.add(deleteButton);
      }

      menuButton.setMenu(menu);
    },

    __itemSelected: function(newVal) {
      const studyBrowserContext = osparc.store.Store.getInstance().getStudyBrowserContext();
      // do not allow selecting workspace
      if (studyBrowserContext !== "trash" && newVal) {
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
      const win = osparc.ui.window.Window.popUpInWindow(folderEditor, title, 300, 120);
      folderEditor.addListener("updateFolder", () => {
        const newName = folderEditor.getLabel();
        const updateData = {
          "name": newName,
          "parentFolderId": folder.getParentFolderId(),
        };
        osparc.store.Folders.getInstance().putFolder(this.getFolderId(), updateData)
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

    __trashFolderRequested: function() {
      const trashDays = osparc.store.StaticInfo.getInstance().getTrashRetentionDays();
      let msg = this.tr("Are you sure you want to move the Folder and all its content to the trash?");
      msg += "<br><br>" + this.tr("It will be permanently deleted after ") + trashDays + " days.";
      const confirmationWin = new osparc.ui.window.Confirmation(msg).set({
        caption: this.tr("Move to Trash"),
        confirmText: this.tr("Move to Trash"),
        confirmAction: "delete"
      });
      confirmationWin.center();
      confirmationWin.open();
      confirmationWin.addListener("close", () => {
        if (confirmationWin.getConfirmed()) {
          this.fireDataEvent("trashFolderRequested", this.getFolderId());
        }
      }, this);
    },

    __deleteFolderRequested: function() {
      const msg = this.tr("Are you sure you want to delete") + " <b>" + this.getTitle() + "</b>?";
      const confirmationWin = new osparc.ui.window.Confirmation(msg).set({
        caption: this.tr("Delete Folder"),
        confirmText: this.tr("Delete"),
        confirmAction: "delete"
      });
      osparc.utils.Utils.setIdToWidget(confirmationWin.getConfirmButton(), "confirmDeleteFolderButton");
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
