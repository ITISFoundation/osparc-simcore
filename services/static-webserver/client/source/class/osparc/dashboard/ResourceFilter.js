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


qx.Class.define("osparc.dashboard.ResourceFilter", {
  extend: qx.ui.core.Widget,

  construct: function(resourceType) {
    this.base(arguments);

    osparc.utils.Utils.setIdToWidget(this, resourceType + "-resourceFilter");

    this.__resourceType = resourceType;
    this.__sharedWithButtons = [];
    this.__tagButtons = [];
    this.__serviceTypeButtons = [];

    this._setLayout(new qx.ui.layout.VBox(15));
    this.__buildLayout();
  },

  events: {
    "trashContext": "qx.event.type.Event",
    "changeTab": "qx.event.type.Data",
    "trashStudyRequested": "qx.event.type.Data",
    "trashFolderRequested": "qx.event.type.Data",
    "changeSharedWith": "qx.event.type.Data",
    "changeSelectedTags": "qx.event.type.Data",
    "changeServiceType": "qx.event.type.Data"
  },

  members: {
    __resourceType: null,
    __workspacesAndFoldersTree: null,
    __trashButton: null,
    __sharedWithButtons: null,
    __tagButtons: null,
    __serviceTypeButtons: null,

    __buildLayout: function() {
      switch (this.__resourceType) {
        case "study":
          this._add(this.__createWorkspacesAndFoldersTree());
          this._add(this.__createTrashBin());
          this._add(this.__createResourceTypeContextButtons());
          this._add(this.__createTagsFilterLayout());
          break;
        case "template":
          this._add(this.__createResourceTypeContextButtons());
          this._add(this.__createSharedWithFilterLayout());
          this._add(this.__createTagsFilterLayout());
          break;
        case "service":
          this._add(this.__createResourceTypeContextButtons());
          this._add(this.__createSharedWithFilterLayout());
          this._add(this.__createServiceTypeFilterLayout());
          break;
      }
    },

    contextChanged: function(context, workspaceId, folderId) {
      this.__workspacesAndFoldersTree.set({
        currentWorkspaceId: workspaceId,
        currentFolderId: folderId,
      });
      this.__workspacesAndFoldersTree.contextChanged(context);

      this.__trashButton.setValue(context === "trash");
    },

    /* WORKSPACES AND FOLDERS */
    __createWorkspacesAndFoldersTree: function() {
      const workspacesAndFoldersTree = this.__workspacesAndFoldersTree = new osparc.dashboard.WorkspacesAndFoldersTree();
      osparc.utils.Utils.setIdToWidget(workspacesAndFoldersTree, "contextTree");
      // Height needs to be calculated manually to make it flexible
      workspacesAndFoldersTree.set({
        minHeight: 60,
        maxHeight: 400,
        height: 60,
      });
      workspacesAndFoldersTree.addListener("openChanged", () => {
        const rowConfig = workspacesAndFoldersTree.getPane().getRowConfig();
        const totalHeight = rowConfig.itemCount * rowConfig.defaultItemSize;
        workspacesAndFoldersTree.setHeight(totalHeight + 10);
      });
      return workspacesAndFoldersTree;
    },

    getWorkspacesAndFoldersTree: function() {
      return this.__workspacesAndFoldersTree;
    },
    /* /WORKSPACES AND FOLDERS */

    /* TRASH BIN */
    __createTrashBin: function() {
      const trashButton = this.__trashButton = new qx.ui.toolbar.RadioButton().set({
        value: false,
        appearance: "filter-toggle-button",
        label: this.tr("Bin"),
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

    /* RESOURCE TYPE CONTEXT */
    __createResourceTypeContextButtons: function() {
      const resourceTypeContextButtons = new qx.ui.container.Composite(new qx.ui.layout.VBox());

      const studiesButton = this.__createStudiesButton().set({
        value: this.__resourceType === "study",
        visibility: this.__resourceType === "study" ? "excluded" : "visible",
      });
      resourceTypeContextButtons.add(studiesButton);

      const permissions = osparc.data.Permissions.getInstance();
      const templatesButton = this.__createTemplatesButton().set({
        value: this.__resourceType === "template",
      });
      if (permissions.canDo("dashboard.templates.read")) {
        resourceTypeContextButtons.add(templatesButton);
      }

      const servicesButton = this.__createServicesButton().set({
        value: this.__resourceType === "service",
      });
      if (permissions.canDo("dashboard.services.read")) {
        resourceTypeContextButtons.add(servicesButton);
      }

      return resourceTypeContextButtons;
    },

    __createStudiesButton: function() {
      const studyAlias = osparc.product.Utils.getStudyAlias({
        firstUpperCase: true,
        plural: true
      });
      const studiesButton = new qx.ui.toolbar.RadioButton().set({
        value: false,
        appearance: "filter-toggle-button",
        label: studyAlias,
        icon: "@FontAwesome5Solid/file/16",
        paddingLeft: 10, // align it with the context
      });
      osparc.utils.Utils.setIdToWidget(studiesButton, "studiesTabBtn");
      studiesButton.addListener("tap", () => {
        studiesButton.setValue(true);
        this.fireDataEvent("changeTab", "studiesTab");
      });
      return studiesButton;
    },

    __createTemplatesButton: function() {
      const templateAlias = osparc.product.Utils.getTemplateAlias({
        firstUpperCase: true,
        plural: true
      });
      const templatesButton = new qx.ui.toolbar.RadioButton().set({
        value: false,
        appearance: "filter-toggle-button",
        label: templateAlias,
        icon: "@FontAwesome5Solid/copy/16",
        paddingLeft: 10, // align it with the context
      });
      osparc.utils.Utils.setIdToWidget(templatesButton, "templatesTabBtn");
      templatesButton.addListener("tap", () => {
        templatesButton.setValue(true);
        this.fireDataEvent("changeTab", "templatesTab");
      });
      return templatesButton;
    },

    __createServicesButton: function() {
      const servicesButton = new qx.ui.toolbar.RadioButton().set({
        value: false,
        appearance: "filter-toggle-button",
        label: this.tr("Services"),
        icon: "@FontAwesome5Solid/cogs/16",
        paddingLeft: 10, // align it with the context
      });
      osparc.utils.Utils.setIdToWidget(servicesButton, "servicesTabBtn");
      servicesButton.addListener("tap", () => {
        servicesButton.setValue(true);
        this.fireDataEvent("changeTab", "servicesTab");
      });
      return servicesButton;
    },
    /* /RESOURCE TYPE CONTEXT */

    /* SHARED WITH */
    __createSharedWithFilterLayout: function() {
      const sharedWithLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

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
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(2)).set({
        marginTop: 20
      });
      osparc.utils.Utils.setIdToWidget(layout, this.__resourceType + "-tagsFilter");

      this.__populateTags(layout, []);
      osparc.store.Tags.getInstance().addListener("tagsChanged", () => {
        this.__populateTags(layout, this.__getSelectedTagIds());
      }, this);

      return layout;
    },

    __getSelectedTagIds: function() {
      const selectedTagIds = this.__tagButtons.filter(btn => btn.getValue()).map(btn => btn.id);
      return selectedTagIds;
    },

    __populateTags: function(layout, selectedTagIds) {
      const maxTags = 5;
      this.__tagButtons = [];
      layout.removeAll();
      osparc.store.Tags.getInstance().getTags().forEach((tag, idx) => {
        const button = new qx.ui.form.ToggleButton(null, "@FontAwesome5Solid/tag/16");
        button.id = tag.getTagId();
        tag.bind("name", button, "label");
        tag.bind("color", button.getChildControl("icon"), "textColor");
        osparc.utils.Utils.setIdToWidget(button, this.__resourceType + "-tagFilterItem");
        button.set({
          appearance: "filter-toggle-button",
          value: selectedTagIds.includes(tag.getTagId())
        });

        layout.add(button);

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
        layout.add(showAllButton);
      }

      const editTagsButton = new qx.ui.form.Button(this.tr("Edit Tags..."), "@FontAwesome5Solid/pencil-alt/14");
      editTagsButton.set({
        appearance: "filter-toggle-button"
      });
      editTagsButton.addListener("execute", () => {
        const preferencesWindow = osparc.desktop.preferences.PreferencesWindow.openWindow();
        preferencesWindow.openTags();
      });
      layout.add(editTagsButton);

      if (this.__resourceType === "study") {
        layout.getChildren().forEach(item => item.setPaddingLeft(10)); // align them with the context
      }
    },
    /* /TAGS */

    /* SERVICE TYPE */
    __createServiceTypeFilterLayout: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      const radioGroup = new qx.ui.form.RadioGroup();
      radioGroup.setAllowEmptySelection(true);

      const serviceTypes = osparc.service.Utils.TYPES;
      Object.keys(serviceTypes).forEach(serviceId => {
        if (!["computational", "dynamic"].includes(serviceId)) {
          return;
        }
        const serviceType = serviceTypes[serviceId];
        const iconSize = 20;
        const button = new qx.ui.toolbar.RadioButton(serviceType.label, serviceType.icon+iconSize);
        button.id = serviceId;
        osparc.utils.Utils.setIdToWidget(button, this.__resourceType + "-serviceTypeFilterItem");
        button.set({
          appearance: "filter-toggle-button",
          value: false
        });

        layout.add(button);
        radioGroup.add(button);

        button.addListener("execute", () => {
          const checked = button.getValue();
          this.fireDataEvent("changeServiceType", {
            id: checked ? serviceId : null,
            label: checked ? serviceType.label : null
          });
        }, this);

        this.__serviceTypeButtons.push(button);
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
      if ("serviceType" in filterData) {
        this.__serviceTypeButtons.forEach(btn => {
          btn.setValue(filterData["serviceType"] === btn.id);
        });
      }
    }
  }
});
