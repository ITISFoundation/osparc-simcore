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


qx.Class.define("osparc.dashboard.ResourceBrowserFilter", {
  extend: qx.ui.core.Widget,

  construct: function(resourceType) {
    this.base(arguments);

    osparc.utils.Utils.setIdToWidget(this, resourceType + "-resourceFilter");

    this.__resourceType = resourceType;
    this.__sharedWithButtons = [];
    this.__tagButtons = [];
    this.__appTypeButtons = [];

    this._setLayout(new qx.ui.layout.VBox(10));
    this.__buildLayout();
  },

  events: {
    "templatesContext": "qx.event.type.Event",
    "publicContext": "qx.event.type.Event",
    "trashContext": "qx.event.type.Event",
    "changeTab": "qx.event.type.Data",
    "trashStudyRequested": "qx.event.type.Data",
    "trashFolderRequested": "qx.event.type.Data",
    "changeSharedWith": "qx.event.type.Data",
    "changeSelectedTags": "qx.event.type.Data",
    "changeAppType": "qx.event.type.Data",
  },

  members: {
    __resourceType: null,
    __workspacesAndFoldersTree: null,
    __templatesButton: null,
    __publicProjectsButton: null,
    __trashButton: null,
    __sharedWithButtons: null,
    __tagButtons: null,
    __appTypeButtons: null,

    __buildLayout: function() {
      const filtersSpacer = new qx.ui.core.Spacer(10, 10);
      switch (this.__resourceType) {
        case "study": {
          this._add(this.__createWorkspacesAndFoldersTree());
          if (osparc.product.Utils.showTemplates()) {
            this._add(this.__createTemplates());
          }
          if (osparc.product.Utils.showPublicProjects()) {
            this._add(this.__createPublicProjects());
          }
          this._add(this.__createTrashBin());
          this._add(filtersSpacer);
          const scrollView = new qx.ui.container.Scroll();
          scrollView.add(this.__createTagsFilterLayout());
          this._add(scrollView, {
            flex: 1
          });
          break;
        }
        case "template": {
          this._add(filtersSpacer);
          this._add(this.__createSharedWithFilterLayout());
          const scrollView = new qx.ui.container.Scroll();
          scrollView.add(this.__createTagsFilterLayout());
          this._add(scrollView, {
            flex: 1
          });
          break;
        }
        case "service":
          this._add(filtersSpacer);
          this._add(this.__createSharedWithFilterLayout());
          this._add(this.__createAppTypeFilterLayout());
          break;
      }
    },

    contextChanged: function(context, workspaceId, folderId) {
      this.__workspacesAndFoldersTree.set({
        currentWorkspaceId: workspaceId,
        currentFolderId: folderId,
      });
      this.__workspacesAndFoldersTree.contextChanged(context);

      this.__templatesButton.setValue(context === "templates");
      this.__publicProjectsButton.setValue(context === "public");
      this.__trashButton.setValue(context === "trash");
    },

    /* WORKSPACES AND FOLDERS */
    __createWorkspacesAndFoldersTree: function() {
      const workspacesAndFoldersTree = this.__workspacesAndFoldersTree = new osparc.dashboard.WorkspacesAndFoldersTree();
      osparc.utils.Utils.setIdToWidget(workspacesAndFoldersTree, "contextTree");
      // Height needs to be calculated manually to make it flexible
      workspacesAndFoldersTree.set({
        minHeight: 60, // two entries
        maxHeight: 400,
        height: 60,
      });
      workspacesAndFoldersTree.addListener("openChanged", () => {
        const rowConfig = workspacesAndFoldersTree.getPane().getRowConfig();
        const totalHeight = rowConfig.itemCount * rowConfig.defaultItemSize;
        workspacesAndFoldersTree.setHeight(totalHeight + 2);
      });
      return workspacesAndFoldersTree;
    },

    getWorkspacesAndFoldersTree: function() {
      return this.__workspacesAndFoldersTree;
    },
    /* /WORKSPACES AND FOLDERS */

    __createTemplates: function() {
      const templatesButton = this.__templatesButton = new qx.ui.toolbar.RadioButton().set({
        value: false,
        appearance: "filter-toggle-button",
        label: this.tr("Templates"),
        icon: "@FontAwesome5Solid/copy/16",
        paddingLeft: 10, // align it with the context
      });
      templatesButton.addListener("changeValue", e => {
        const templatesEnabled = e.getData();
        if (templatesEnabled) {
          this.fireEvent("templatesContext");
        }
      });
      return templatesButton;
    },

    __createPublicProjects: function() {
      const publicProjectsButton = this.__publicProjectsButton = new qx.ui.toolbar.RadioButton().set({
        value: false,
        appearance: "filter-toggle-button",
        label: this.tr("Public Projects"),
        icon: "@FontAwesome5Solid/globe/16",
        paddingLeft: 10, // align it with the context
      });
      publicProjectsButton.addListener("changeValue", e => {
        const templatesEnabled = e.getData();
        if (templatesEnabled) {
          this.fireEvent("publicContext");
        }
      });
      return publicProjectsButton;
    },

    /* TRASH BIN */
    __createTrashBin: function() {
      const trashButton = this.__trashButton = new qx.ui.toolbar.RadioButton().set({
        value: false,
        appearance: "filter-toggle-button",
        label: this.tr("Recently Deleted"),
        icon: "@FontAwesome5Solid/trash-alt/16",
        paddingLeft: 10, // align it with the context
      });
      trashButton.addListener("changeValue", e => {
        const trashEnabled = e.getData();
        if (trashEnabled) {
          this.fireEvent("trashContext");
        }
      });
      this.evaluateTrashEmpty();
      this.__attachDropHandlers(trashButton);
      return trashButton;
    },

    __attachDropHandlers: function(trashButton) {
      trashButton.setDroppable(true);

      trashButton.addListener("dragover", e => {
        if (e.supportsType("osparc-moveStudy")) {
          osparc.dashboard.DragDropHelpers.trashStudy.dragOver(e);
        } else if (e.supportsType("osparc-moveFolder")) {
          osparc.dashboard.DragDropHelpers.trashFolder.dragOver(e);
        }
      });

      trashButton.addListener("dragleave", () => {
        osparc.dashboard.DragDropHelpers.dragLeave();
      });

      trashButton.addListener("drop", e => {
        if (e.supportsType("osparc-moveStudy")) {
          const studyData = osparc.dashboard.DragDropHelpers.trashStudy.drop(e);
          this.fireDataEvent("trashStudyRequested", studyData);
        } else if (e.supportsType("osparc-moveFolder")) {
          const folderId = osparc.dashboard.DragDropHelpers.trashFolder.drop(e);
          this.fireDataEvent("trashFolderRequested", folderId);
        }
      });
    },

    evaluateTrashEmpty: function() {
      if (osparc.auth.Data.getInstance().isGuest()) {
        // Guests do not have access to folders and workspaces
        return;
      }

      const studiesParams = {
        url: {
          offset: 0,
          limit: 1, // just one
          orderBy: JSON.stringify({
            field: "last_change_date",
            direction: "desc"
          }),
        }
      };
      const foldersParams = {
        url: {
          offset: 0,
          limit: 1, // just one
          orderBy: JSON.stringify({
            field: "modified_at",
            direction: "desc"
          }),
        }
      };
      const workspacesParams = {
        url: {
          offset: 0,
          limit: 1, // just one
          orderBy: JSON.stringify({
            field: "modified_at",
            direction: "desc"
          }),
        }
      };
      Promise.all([
        osparc.data.Resources.fetch("studies", "getPageTrashed", studiesParams),
        osparc.data.Resources.fetch("folders", "getPageTrashed", foldersParams),
        osparc.data.Resources.fetch("workspaces", "getPageTrashed", workspacesParams),
      ])
        .then(values => {
          const nTrashedStudies = values[0].length;
          const nTrashedFolders = values[1].length;
          const nTrashedWorkspaces = values[2].length;
          this.setTrashEmpty((nTrashedStudies+nTrashedFolders+nTrashedWorkspaces) === 0);
        })
        .catch(err => console.error(err));
    },

    setTrashEmpty: function(isEmpty) {
      this.__trashButton.set({
        icon: isEmpty ? "@FontAwesome5Solid/trash-alt/16" : "@FontAwesome5Solid/trash/16"
      });
    },
    /* /TRASH BIN */

    /* SHARED WITH */
    __createSharedWithFilterLayout: function() {
      const sharedWithLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(2));

      const sharedWithRadioGroup = new qx.ui.form.RadioGroup();
      sharedWithRadioGroup.setAllowEmptySelection(false);

      const options = osparc.dashboard.SearchBarFilter.getSharedWithOptions(this.__resourceType);
      options.forEach(option => {
        if (this.__resourceType === "study" && option.id === "shared-with-everyone") {
          return;
        }
        const button = new qx.ui.toolbar.RadioButton().set({
          appearance: "filter-toggle-button",
          label: option.label,
          icon: option.icon,
        });
        osparc.utils.Utils.setIdToWidget(button, this.__resourceType + "-sharedWithFilterItem");
        if (this.__resourceType === "study") {
          if (option.id === "show-all") {
            button.set({
              label: this.tr("My Workspace")
            });
          } else if (option.id === "shared-with-me") {
            button.set({
              label: this.tr("Shared") + " " + osparc.product.Utils.getStudyAlias({
                firstUpperCase: true,
                plural: true,
              })
            });
          }
        }
        button.id = option.id;

        sharedWithLayout.add(button);
        sharedWithRadioGroup.add(button);

        button.addListener("execute", () => {
          this.fireDataEvent("changeSharedWith", {
            id: option.id,
            label: option.label
          });
        }, this);

        this.__sharedWithButtons.push(button);
      });

      return sharedWithLayout;
    },
    /* /SHARED WITH */

    /* TAGS */
    __createTagsFilterLayout: function() {
      const tagsLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(2));
      osparc.utils.Utils.setIdToWidget(tagsLayout, this.__resourceType + "-tagsFilter");

      this.__populateTags(tagsLayout, []);
      osparc.store.Tags.getInstance().addListener("tagsChanged", () => {
        this.__populateTags(tagsLayout, this.__getSelectedTagIds());
      }, this);

      return tagsLayout;
    },

    __getSelectedTagIds: function() {
      const selectedTagIds = this.__tagButtons.filter(btn => btn.getValue()).map(btn => btn.id);
      return selectedTagIds;
    },

    __populateTags: function(tagsLayout, selectedTagIds) {
      const maxTags = 5;
      this.__tagButtons = [];
      tagsLayout.removeAll();
      osparc.store.Tags.getInstance().getTags().forEach((tag, idx) => {
        const button = new qx.ui.form.ToggleButton(null, "@FontAwesome5Solid/tag/16");
        button.id = tag.getTagId();
        tag.bind("name", button, "label");
        tag.bind("name", button, "toolTipText");
        tag.bind("color", button.getChildControl("icon"), "textColor");
        osparc.utils.Utils.setIdToWidget(button, this.__resourceType + "-tagFilterItem");
        button.set({
          appearance: "filter-toggle-button",
          value: selectedTagIds.includes(tag.getTagId())
        });

        tagsLayout.add(button);

        button.addListener("execute", () => {
          const selection = this.__getSelectedTagIds();
          this.fireDataEvent("changeSelectedTags", selection);
        }, this);

        button.setVisibility(idx >= maxTags ? "excluded" : "visible");

        this.__tagButtons.push(button);
      });


      if (this.__tagButtons.length > maxTags) {
        const showAllButton = new qx.ui.form.Button(this.tr("All Tags..."), "@FontAwesome5Solid/tags/16");
        showAllButton.set({
          appearance: "filter-toggle-button"
        });
        showAllButton.showingAll = false;
        showAllButton.addListener("execute", () => {
          if (showAllButton.showingAll) {
            this.__tagButtons.forEach((btn, idx) => btn.setVisibility(idx >= maxTags ? "excluded" : "visible"));
            showAllButton.setLabel(this.tr("All Tags..."));
            showAllButton.showingAll = false;
          } else {
            this.__tagButtons.forEach(btn => btn.setVisibility("visible"));
            showAllButton.setLabel(this.tr("Less Tags..."));
            showAllButton.showingAll = true;
          }
        });
        tagsLayout.add(showAllButton);
      }

      const editTagsButton = new qx.ui.form.Button(this.tr("Edit Tags..."), "@FontAwesome5Solid/pencil-alt/14");
      editTagsButton.set({
        appearance: "filter-toggle-button"
      });
      editTagsButton.addListener("execute", () => {
        const myAccountWindow = osparc.desktop.account.MyAccountWindow.openWindow();
        myAccountWindow.openTags();
      });
      tagsLayout.add(editTagsButton);

      if (this.__resourceType === "study") {
        tagsLayout.getChildren().forEach(item => item.setPaddingLeft(10)); // align them with the context
      }
    },
    /* /TAGS */

    /* SERVICE TYPE */
    __createAppTypeFilterLayout: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(2));

      const radioGroup = new qx.ui.form.RadioGroup();
      radioGroup.setAllowEmptySelection(true);

      const iconSize = 20;
      const serviceTypes = osparc.service.Utils.TYPES;
      Object.keys(serviceTypes).forEach(serviceId => {
        if (!["computational", "dynamic"].includes(serviceId)) {
          return;
        }
        const serviceType = serviceTypes[serviceId];
        const button = new qx.ui.toolbar.RadioButton(serviceType.label, serviceType.icon+iconSize);
        button.appType = serviceId;
        osparc.utils.Utils.setIdToWidget(button, this.__resourceType + "-serviceTypeFilterItem");
        this.__appTypeButtons.push(button);
      });

      // hypertools filter
      const button = new qx.ui.toolbar.RadioButton("Hypertools", null);
      osparc.utils.Utils.replaceIconWithThumbnail(button, osparc.data.model.StudyUI.HYPERTOOL_ICON(18), 20);
      button.appType = "hypertool";
      this.__appTypeButtons.push(button);

      this.__appTypeButtons.forEach(btn => {
        btn.set({
          appearance: "filter-toggle-button",
          value: false
        });
        layout.add(btn);
        radioGroup.add(btn);
        btn.addListener("execute", () => {
          const checked = btn.getValue();
          this.fireDataEvent("changeAppType", {
            appType: checked ? btn.appType : null,
            label: checked ? btn.getLabel() : null
          });
        }, this);
      });

      return layout;
    },
    /* /SERVICE TYPE */

    filterChanged: function(filterData) {
      if ("sharedWith" in filterData) {
        const foundBtn = this.__sharedWithButtons.find(btn => btn.id === filterData["sharedWith"]);
        if (foundBtn) {
          foundBtn.setValue(true);
        }
      }
      if ("tags" in filterData) {
        this.__tagButtons.forEach(btn => {
          btn.setValue(filterData["tags"].includes(btn.id));
        });
      }
      if ("appType" in filterData) {
        this.__appTypeButtons.forEach(btn => {
          btn.setValue(filterData["appType"] === btn.appType);
        });
      }
    }
  }
});
