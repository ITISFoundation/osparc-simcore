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
 * Widget used for displaying a Workspace in the Study Browser
 *
 */

qx.Class.define("osparc.dashboard.WorkspaceButtonItem", {
  extend: osparc.dashboard.WorkspaceButtonBase,

  /**
    * @param workspace {osparc.data.model.Workspace}
    */
  construct: function(workspace) {
    this.base(arguments);

    this.set({
      appearance: "pb-listitem"
    });

    this.addListener("tap", this.__itemSelected, this);

    this.setPriority(osparc.dashboard.CardBase.CARD_PRIORITY.ITEM);

    this.set({
      workspace: workspace
    });
  },

  events: {
    "workspaceSelected": "qx.event.type.Data",
    "workspaceUpdated": "qx.event.type.Data",
    "trashWorkspaceRequested": "qx.event.type.Data",
    "untrashWorkspaceRequested": "qx.event.type.Data",
    "deleteWorkspaceRequested": "qx.event.type.Data",
  },

  properties: {
    workspace: {
      check: "osparc.data.model.Workspace",
      nullable: false,
      init: null,
      apply: "__applyWorkspace"
    },

    workspaceId: {
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

    myAccessRights: {
      check: "Object",
      nullable: true,
      apply: "__applyMyAccessRights"
    },

    accessRights: {
      check: "Object",
      nullable: true,
      apply: "__applyAccessRights"
    },

    modifiedAt: {
      check: "Date",
      nullable: true,
      apply: "__applyModifiedAt"
    },

    trashedAt: {
      check: "Date",
      nullable: true,
      apply: "__applyTrashedAt"
    },

    trashedBy: {
      check: "Number",
      nullable: true,
      apply: "__applyTrashedBy"
    },
  },

  statics: {
    MENU_BTN_DIMENSIONS: 24
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      let layout;
      switch (id) {
        case "shared-icon":
          control = new qx.ui.basic.Image().set({
            alignY: "middle",
            allowGrowX: false,
            allowShrinkX: false
          });
          layout = this.getChildControl("header");
          layout.addAt(control, osparc.dashboard.WorkspaceButtonBase.HPOS.SHARED);
          break;
        case "menu-button":
          control = new qx.ui.form.MenuButton().set({
            appearance: "form-button-outlined",
            minWidth: this.self().MENU_BTN_DIMENSIONS,
            minHeight: this.self().MENU_BTN_DIMENSIONS,
            width: this.self().MENU_BTN_DIMENSIONS,
            height: this.self().MENU_BTN_DIMENSIONS,
            padding: [0, 8, 0, 8],
            alignX: "center",
            alignY: "middle",
            icon: "@FontAwesome5Solid/ellipsis-v/14",
            focusable: false
          });
          // make it circular
          control.getContentElement().setStyles({
            "border-radius": `${this.self().MENU_BTN_DIMENSIONS / 2}px`
          });
          osparc.utils.Utils.setIdToWidget(control, "workspaceItemMenuButton");
          layout = this.getChildControl("header");
          layout.addAt(control, osparc.dashboard.WorkspaceButtonBase.HPOS.MENU);
          break;
        case "date-by":
          control = new osparc.ui.basic.DateAndBy();
          layout = this.getChildControl("footer");
          layout.addAt(control, osparc.dashboard.WorkspaceButtonBase.FPOS.DATE);
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyWorkspace: function(workspace) {
      this.set({
        cardKey: "workspace-" + workspace.getWorkspaceId()
      });
      workspace.bind("workspaceId", this, "workspaceId");
      workspace.bind("name", this, "title");
      workspace.bind("description", this, "description");
      workspace.bind("thumbnail", this, "thumbnail", {
        converter: thumbnail => thumbnail ? thumbnail : osparc.store.Workspaces.iconPath(-1)
      });
      workspace.bind("accessRights", this, "accessRights");
      workspace.bind("modifiedAt", this, "modifiedAt");
      workspace.bind("trashedAt", this, "trashedAt");
      workspace.bind("trashedBy", this, "trashedBy");
      workspace.bind("myAccessRights", this, "myAccessRights");

      osparc.utils.Utils.setIdToWidget(this, "workspaceItem_" + workspace.getWorkspaceId());
    },

    __applyTitle: function(value) {
      const label = this.getChildControl("title");
      label.setValue(value);
      this.__updateTooltip();
    },

    __applyDescription: function() {
      this.__updateTooltip();
    },

    __applyMyAccessRights: function(value) {
      if (value && value["delete"]) {
        const menuButton = this.getChildControl("menu-button");
        menuButton.setVisibility("visible");

        const menu = new qx.ui.menu.Menu().set({
          appearance: "menu-wider",
          position: "bottom-right",
        });

        const studyBrowserContext = osparc.store.Store.getInstance().getStudyBrowserContext();
        if (
          studyBrowserContext === osparc.dashboard.StudyBrowser.CONTEXT.SEARCH_PROJECTS ||
          studyBrowserContext === osparc.dashboard.StudyBrowser.CONTEXT.WORKSPACES
        ) {
          const editButton = new qx.ui.menu.Button(this.tr("Edit..."), "@FontAwesome5Solid/pencil-alt/12");
          editButton.addListener("execute", () => {
            const workspace = this.getWorkspace();
            const workspaceEditor = new osparc.editor.WorkspaceEditor(workspace);
            const title = this.tr("Edit Workspace");
            const win = osparc.ui.window.Window.popUpInWindow(workspaceEditor, title, 300, 150);
            workspaceEditor.addListener("workspaceUpdated", () => {
              win.close();
              this.fireDataEvent("workspaceUpdated", workspace.getWorkspaceId());
            });
            workspaceEditor.addListener("cancel", () => win.close());
          });
          menu.add(editButton);

          const shareButton = new qx.ui.menu.Button(this.tr("Share..."), "@FontAwesome5Solid/share-alt/12");
          shareButton.addListener("execute", () => this.__openShareWith(), this);
          menu.add(shareButton);

          menu.addSeparator();

          const trashButton = new qx.ui.menu.Button(this.tr("Delete"), "@FontAwesome5Solid/trash/12");
          trashButton.addListener("execute", () => this.__trashWorkspaceRequested(), this);
          menu.add(trashButton);
        } else if (studyBrowserContext === osparc.dashboard.StudyBrowser.CONTEXT.TRASH) {
          const restoreButton = new qx.ui.menu.Button(this.tr("Restore"), "@MaterialIcons/restore_from_trash/16");
          restoreButton.addListener("execute", () => this.fireDataEvent("untrashWorkspaceRequested", this.getWorkspace()), this);
          menu.add(restoreButton);

          menu.addSeparator();

          const deleteButton = new qx.ui.menu.Button(this.tr("Delete permanently"), "@FontAwesome5Solid/trash/12");
          osparc.utils.Utils.setIdToWidget(deleteButton, "deleteWorkspaceMenuItem");
          deleteButton.addListener("execute", () => this.__deleteWorkspaceRequested(), this);
          menu.add(deleteButton);
        }
        menuButton.setMenu(menu);
      }
    },

    __applyAccessRights: function(value) {
      if (value && Object.keys(value).length) {
        const shareIcon = this.getChildControl("shared-icon");
        shareIcon.addListener("tap", e => {
          e.stopPropagation();
          this.__openShareWith();
        }, this);
        shareIcon.addListener("pointerdown", e => e.stopPropagation());
        osparc.dashboard.CardBase.populateShareIcon(shareIcon, value);
      }
    },

    __applyModifiedAt: function(value) {
      if (value) {
        const dateBy = this.getChildControl("date-by");
        dateBy.set({
          date: value,
          toolTipText: this.tr("Last modified"),
        })
      }
    },

    __applyTrashedAt: function(value) {
      if (value && value.getTime() !== new Date(0).getTime()) {
        const dateBy = this.getChildControl("date-by");
        dateBy.set({
          date: value,
          toolTipText: this.tr("Deleted"),
        });
      }
    },

    __applyTrashedBy: function(gid) {
      if (gid) {
        const dateBy = this.getChildControl("date-by");
        dateBy.setGroupId(gid);
      }
    },

    __updateTooltip: function() {
      const toolTipText = this.getTitle() + (this.getDescription() ? "<br>" + this.getDescription() : "");
      const title = this.getChildControl("title");
      title.set({
        toolTipText
      })
    },

    __itemSelected: function() {
      const studyBrowserContext = osparc.store.Store.getInstance().getStudyBrowserContext();
      // do not allow selecting workspace
      if (studyBrowserContext !== osparc.dashboard.StudyBrowser.CONTEXT.TRASH) {
        this.fireDataEvent("workspaceSelected", this.getWorkspaceId());
      }
    },

    __openShareWith: function() {
      const collaboratorsView = new osparc.share.CollaboratorsWorkspace(this.getWorkspace());
      const title = this.tr("Share Workspace");
      osparc.ui.window.Window.popUpInWindow(collaboratorsView, title, 500, 400);
      collaboratorsView.addListener("updateAccessRights", () => this.__applyAccessRights(this.getWorkspace().getAccessRights()), this);
    },

    __trashWorkspaceRequested: function() {
      const trashDays = osparc.store.StaticInfo.getInstance().getTrashRetentionDays();
      let msg = this.tr("Are you sure you want to delete the Workspace and all its content?");
      msg += "<br><br>" + this.tr("It will be permanently deleted after ") + trashDays + " days.";
      const confirmationWin = new osparc.ui.window.Confirmation(msg).set({
        caption: this.tr("Delete"),
        confirmText: this.tr("Delete"),
        confirmAction: "delete"
      });
      confirmationWin.center();
      confirmationWin.open();
      confirmationWin.addListener("close", () => {
        if (confirmationWin.getConfirmed()) {
          this.fireDataEvent("trashWorkspaceRequested", this.getWorkspaceId());
        }
      }, this);
    },

    __deleteWorkspaceRequested: function() {
      let msg = this.tr("Are you sure you want to delete") + " <b>" + this.getTitle() + "</b>?";
      msg += "<br>" + this.tr("All the content of the workspace will be deleted.");
      const confirmationWin = new osparc.ui.window.Confirmation(msg).set({
        caption: this.tr("Delete Workspace"),
        confirmText: this.tr("Delete permanently"),
        confirmAction: "delete"
      });
      osparc.utils.Utils.setIdToWidget(confirmationWin.getConfirmButton(), "confirmDeleteWorkspaceButton");
      confirmationWin.center();
      confirmationWin.open();
      confirmationWin.addListener("close", () => {
        if (confirmationWin.getConfirmed()) {
          this.fireDataEvent("deleteWorkspaceRequested", this.getWorkspaceId());
        }
      }, this);
    }
  }
});
