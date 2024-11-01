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
 * Widget used for displaying a Workspace information
 *
 */

qx.Class.define("osparc.dashboard.StudyBrowserHeader", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(10));

    this.set({
      minHeight: this.self().HEIGHT,
      maxHeight: this.self().HEIGHT,
      height: this.self().HEIGHT,
      alignY: "middle",
    });

    this.__spacers = [];

    this.initCurrentWorkspaceId();
    this.initCurrentFolderId();
  },

  events: {
    "locationChanged": "qx.event.type.Data",
    "workspaceUpdated": "qx.event.type.Data",
    "deleteWorkspaceRequested": "qx.event.type.Data"
  },

  properties: {
    currentContext: {
      check: ["studiesAndFolders", "workspaces", "search"],
      nullable: false,
      init: "studiesAndFolders",
      event: "changeCurrentContext",
      apply: "__buildLayout"
    },

    currentWorkspaceId: {
      check: "Number",
      nullable: true,
      init: null,
      event: "changeCurrentWorkspaceId",
      apply: "__buildLayout"
    },

    currentFolderId: {
      check: "Number",
      nullable: true,
      init: null,
      event: "changeCurrentFolderId",
    },

    accessRights: {
      check: "Object",
      nullable: false,
      init: {},
      event: "changeAccessRights",
      apply: "__applyAccessRights"
    },

    myAccessRights: {
      check: "Object",
      nullable: false,
      init: {},
      event: "changeMyAccessRights",
      apply: "__applyMyAccessRights"
    }
  },

  statics: {
    HEIGHT: 36
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon":
          control = new osparc.ui.basic.Thumbnail(null, this.self().HEIGHT, this.self().HEIGHT);
          control.getChildControl("image").set({
            anonymous: true,
            alignY: "middle",
            alignX: "center",
            allowGrowX: true,
            allowGrowY: true,
            decorator: "rounded",
          });
          this._add(control);
          break;
        case "workspace-title":
          control = new qx.ui.basic.Label().set({
            font: "text-16",
            alignY: "middle",
          });
          this._add(control);
          break;
        case "breadcrumbs":
          control = new osparc.dashboard.ContextBreadcrumbs();
          this.bind("currentWorkspaceId", control, "currentWorkspaceId");
          this.bind("currentFolderId", control, "currentFolderId");
          this.bind("currentContext", control, "currentContext");
          control.bind("currentWorkspaceId", this, "currentWorkspaceId");
          control.bind("currentFolderId", this, "currentFolderId");
          control.addListener("locationChanged", e => {
            this.fireDataEvent("locationChanged", e.getData())
          });
          this._add(control);
          break;
        case "edit-button":
          control = new qx.ui.form.MenuButton().set({
            appearance: "form-button-outlined",
            backgroundColor: "transparent",
            padding: [0, 8],
            maxWidth: 22,
            maxHeight: 22,
            icon: "@FontAwesome5Solid/ellipsis-v/8",
            focusable: false,
            alignY: "middle",
          });
          // make it circular
          control.getContentElement().setStyles({
            "border-radius": `${22 / 2}px`
          });
          this._add(control);
          break;
        case "share-layout":
          this.__addSpacer();
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
            alignY: "middle"
          }));
          this._add(control);
          break;
        case "share-text": {
          control = new qx.ui.basic.Label().set({
            font: "text-14"
          });
          const layout = this.getChildControl("share-layout");
          layout.addAt(control, 1);
          break;
        }
        case "role-layout":
          this.__addSpacer();
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
            alignY: "middle"
          }));
          this._add(control);
          break;
        case "role-text": {
          control = new qx.ui.basic.Label().set({
            font: "text-14"
          });
          const layout = this.getChildControl("role-layout");
          layout.addAt(control, 0);
          break;
        }
        case "role-icon": {
          control = osparc.data.Roles.createRolesWorkspaceInfo(false);
          const layout = this.getChildControl("role-layout");
          layout.addAt(control, 1);
          break;
        }
      }

      return control || this.base(arguments, id);
    },

    __titleTapped: function() {
      const workspaceId = this.getCurrentWorkspaceId();
      const folderId = null;
      this.setCurrentFolderId(folderId);
      this.fireDataEvent("locationChanged", {
        workspaceId,
        folderId,
      });
    },

    __buildLayout: function() {
      this.getChildControl("icon");
      const title = this.getChildControl("workspace-title");
      title.resetCursor();
      title.removeListener("tap", this.__titleTapped, this);
      this.getChildControl("breadcrumbs");
      this.getChildControl("edit-button").exclude();
      this.resetAccessRights();
      this.resetMyAccessRights();

      const currentContext = this.getCurrentContext();
      if (currentContext === "search") {
        this.__setIcon("@FontAwesome5Solid/search/24");
        title.set({
          value: this.tr("Search results"),
        });
      } else if (currentContext === "workspaces") {
        this.__setIcon(osparc.store.Workspaces.iconPath(32));
        title.set({
          value: this.tr("Shared Workspaces"),
        })
      } else if (currentContext === "studiesAndFolders") {
        const workspaceId = this.getCurrentWorkspaceId();
        title.setCursor("pointer");
        title.addListener("tap", this.__titleTapped, this);
        const workspace = osparc.store.Workspaces.getInstance().getWorkspace(workspaceId);
        if (workspace) {
          const thumbnail = workspace.getThumbnail();
          this.__setIcon(thumbnail ? thumbnail : osparc.store.Workspaces.iconPath(32));
          workspace.bind("name", title, "value");
          workspace.bind("accessRights", this, "accessRights");
          workspace.bind("myAccessRights", this, "myAccessRights");
        } else {
          this.__setIcon("@FontAwesome5Solid/home/30");
          title.setValue(this.tr("My Workspace"));
        }
      }
    },

    __addSpacer: function() {
      const spacer = new qx.ui.basic.Label("-").set({
        font: "text-16",
        alignY: "middle",
      });
      this.__spacers.push(spacer);
      this._add(spacer);
    },

    __resetIcon: function() {
      const icon = this.getChildControl("icon");
      const image = icon.getChildControl("image");
      image.resetSource();
      icon.getContentElement().setStyles({
        "background-image": "none"
      });
    },

    __setIcon: function(source) {
      this.__resetIcon();

      const icon = this.getChildControl("icon");
      if (source.includes("@")) {
        const image = icon.getChildControl("image");
        image.set({
          source
        });
      } else {
        icon.getContentElement().setStyles({
          "background-image": `url(${source})`,
          "background-repeat": "no-repeat",
          "background-size": "cover",
          "background-position": "center center",
          "background-origin": "border-box"
        });
      }
    },

    __showSpacers: function(show) {
      this.__spacers.forEach(spacer => spacer.setVisibility(show ? "visible" : "excluded"));
    },

    __getShareIcon: function() {
      // reset previous
      const layout = this.getChildControl("share-layout");
      if (this.__shareIcon) {
        layout.remove(this.__shareIcon);
      }

      const shareIcon = this.__shareIcon = new qx.ui.basic.Image().set({
        alignY: "middle",
        allowGrowX: false,
        allowShrinkX: false
      });
      layout.addAt(shareIcon, 0);
      return shareIcon;
    },

    __applyAccessRights: function(accessRights) {
      const shareIcon = this.__getShareIcon();
      const shareText = this.getChildControl("share-text");
      if (accessRights && Object.keys(accessRights).length) {
        osparc.dashboard.CardBase.populateShareIcon(shareIcon, accessRights);
        shareText.setValue(Object.keys(accessRights).length + " members");
        shareIcon.show();
        shareText.show();
        this.__showSpacers(true);
      } else {
        shareIcon.exclude();
        shareText.exclude();
        this.__showSpacers(false);
      }
    },

    __applyMyAccessRights: function(value) {
      const editButton = this.getChildControl("edit-button");
      const roleText = this.getChildControl("role-text");
      const roleIcon = this.getChildControl("role-icon");
      if (value && Object.keys(value).length) {
        editButton.setVisibility(value["delete"] ? "visible" : "excluded");
        const menu = new qx.ui.menu.Menu().set({
          position: "bottom-right"
        });
        const edit = new qx.ui.menu.Button(this.tr("Edit..."), "@FontAwesome5Solid/pencil-alt/12");
        edit.addListener("execute", () => this.__editWorkspace(), this);
        menu.add(edit);
        const share = new qx.ui.menu.Button(this.tr("Share..."), "@FontAwesome5Solid/share-alt/12");
        share.addListener("execute", () => this.__openShareWith(), this);
        menu.add(share);
        editButton.setMenu(menu);
        const val = value["read"] + value["write"] + value["delete"];
        roleText.setValue(osparc.data.Roles.WORKSPACE[val].label);
        roleText.show();
        roleIcon.show();
        this.__showSpacers(true);
      } else {
        editButton.exclude();
        roleText.exclude();
        roleIcon.exclude();
        this.__showSpacers(false);
      }
    },

    __editWorkspace: function() {
      const workspace = osparc.store.Workspaces.getInstance().getWorkspace(this.getCurrentWorkspaceId());
      const permissionsView = new osparc.editor.WorkspaceEditor(workspace);
      const title = this.tr("Edit Workspace");
      const win = osparc.ui.window.Window.popUpInWindow(permissionsView, title, 300, 200);
      permissionsView.addListener("workspaceUpdated", () => {
        win.close();
        this.__buildLayout();
      }, this);
    },

    __openShareWith: function() {
      const workspace = osparc.store.Workspaces.getInstance().getWorkspace(this.getCurrentWorkspaceId());
      const permissionsView = new osparc.share.CollaboratorsWorkspace(workspace);
      const title = this.tr("Share Workspace");
      const win = osparc.ui.window.Window.popUpInWindow(permissionsView, title, 500, 400);
      permissionsView.addListener("updateAccessRights", () => {
        win.close();
        this.__applyAccessRights(workspace.getAccessRights());
      }, this);
    },
  }
});
