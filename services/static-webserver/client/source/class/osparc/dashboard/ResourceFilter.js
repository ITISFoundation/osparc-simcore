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

    osparc.utils.Utils.setIdToWidget(this, "resourceFilter");

    this.__resourceType = resourceType;
    this.__sharedWithButtons = [];
    this.__workspaceButtons = [];
    this.__tagButtons = [];
    this.__serviceTypeButtons = [];

    this._setLayout(new qx.ui.layout.VBox());
    this.__buildLayout();
  },

  events: {
    "changeSharedWith": "qx.event.type.Data",
    "changeWorkspace": "qx.event.type.Data",
    "changeSelectedTags": "qx.event.type.Data",
    "changeServiceType": "qx.event.type.Data"
  },

  members: {
    __resourceType: null,
    __sharedWithButtons: null,
    __workspaceButtons: null,
    __tagButtons: null,
    __serviceTypeButtons: null,

    __buildLayout: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(40));

      layout.add(this.__createSharedWithFilterLayout());

      if (this.__resourceType !== "service") {
        layout.add(this.__createTagsFilterLayout());
      }

      if (this.__resourceType === "service") {
        layout.add(this.__createServiceTypeFilterLayout());
      }

      const scrollContainer = new qx.ui.container.Scroll();
      scrollContainer.add(layout);
      this._add(scrollContainer, {
        flex: 1
      });
    },

    /* SHARED WITH */
    __createSharedWithFilterLayout: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      const radioGroup = new qx.ui.form.RadioGroup();
      radioGroup.setAllowEmptySelection(false);

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
        if (this.__resourceType === "study") {
          if (option.id === "show-all") {
            button.set({
              label: this.tr("My Workspace")
            });
          } else {
            button.set({
              marginLeft: 15
            });
          }
        }
        button.id = option.id;

        layout.add(button);
        radioGroup.add(button);

        button.addListener("execute", () => {
          this.fireDataEvent("changeSharedWith", {
            id: option.id,
            label: option.label
          });
        }, this);

        this.__sharedWithButtons.push(button);
      });

      if (this.__resourceType === "study") {
        this.__addWorkspaceButtons(layout, radioGroup);
      }

      return layout;
    },
    /* /SHARED WITH */

    /* WORKSPACES */
    __addWorkspaceButtons: function(layout, radioGroup) {
      layout.add(new qx.ui.core.Spacer());
      const workspacesButton = new qx.ui.toolbar.RadioButton(this.tr("Shared Workspaces"), osparc.store.Workspaces.iconPath(22));
      workspacesButton.workspaceId = -1;
      workspacesButton.set({
        appearance: "filter-toggle-button"
      });
      layout.add(workspacesButton);
      radioGroup.add(workspacesButton);
      workspacesButton.addListener("execute", () => {
        this.fireDataEvent("changeWorkspace", workspacesButton.workspaceId);
      });

      osparc.store.Workspaces.fetchWorkspaces()
        .then(workspaces => {
          workspaces.forEach(workspace => {
            const workspaceButton = new qx.ui.toolbar.RadioButton(workspace.getName(), osparc.store.Workspaces.iconPath(22));
            workspaceButton.workspaceId = workspace.getWorkspaceId();
            this.__workspaceButtons.push(workspaceButton);
            workspaceButton.set({
              appearance: "filter-toggle-button",
              marginLeft: 15,
            });
            layout.add(workspaceButton);
            radioGroup.add(workspaceButton);
            workspaceButton.addListener("execute", () => {
              this.fireDataEvent("changeWorkspace", workspaceButton.workspaceId);
            }, this);
          });
        })
        .catch(console.error);
    },

    workspaceSelected: function(workspaceId) {
      const foundButton = this.__workspaceButtons.find(workspaceButton => workspaceButton.workspaceId === workspaceId);
      if (foundButton) {
        foundButton.execute();
      }
    },
    /* /WORKSPACES */

    /* TAGS */
    __createTagsFilterLayout: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      this.__populateTags(layout, []);
      osparc.store.Store.getInstance().addListener("changeTags", () => {
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
      osparc.store.Store.getInstance().getTags().forEach((tag, idx) => {
        const button = new qx.ui.form.ToggleButton(tag.name, "@FontAwesome5Solid/tag/20");
        button.id = tag.id;
        button.set({
          appearance: "filter-toggle-button",
          value: selectedTagIds.includes(tag.id)
        });
        button.getChildControl("icon").set({
          textColor: tag.color
        });

        layout.add(button);

        button.addListener("execute", () => {
          const selection = this.__getSelectedTagIds();
          this.fireDataEvent("changeSelectedTags", selection);
        }, this);

        button.setVisibility(idx >= maxTags ? "excluded" : "visible");

        this.__tagButtons.push(button);
      });


      if (this.__tagButtons.length >= maxTags) {
        const showAllButton = new qx.ui.form.Button(this.tr("All Tags..."), "@FontAwesome5Solid/tags/20");
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
