/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.dashboard.SearchBarFilter", {
  extend: osparc.filter.UIFilter,

  construct: function(resourceType) {
    this.__resourceType = resourceType;

    this.base(arguments, "searchBarFilter-"+resourceType, "searchBarFilter");

    this._setLayout(new qx.ui.layout.HBox(5));

    this.set({
      backgroundColor: this.self().BG_COLOR,
      paddingLeft: 6,
      height: this.self().HEIGHT,
      maxHeight: this.self().HEIGHT,
      decorator: "rounded",
    });

    this.__buildLayout();

    this.__buildFiltersMenu();
    osparc.store.Store.getInstance().addListener("changeTags", () => this.__buildFiltersMenu(), this);

    this.__currentFilter = null;
  },

  properties: {
    showFilterMenu: {
      check: "Boolean",
      init: true,
      event: "changeShowFilterMenu",
    },

    activeFilters: {
      check: "Object",
      init: {},
      nullable: false,
      event: "changeActiveFilters",
      apply: "__applyActiveFilters",
    },
  },

  statics: {
    HEIGHT: 36,
    BG_COLOR: "input-background",

    getInitialFilterData: function() {
      return {
        tags: [],
        sharedWith: null,
        appType: null,
        text: ""
      };
    },

    getSharedWithOptions: function(resourceType) {
      if (resourceType === "template") {
        resourceType = "tutorial";
      }

      const resourceAlias = osparc.product.Utils.resourceTypeToAlias(resourceType, {
        firstUpperCase: true,
        plural: true
      });
      return [{
        id: "show-all",
        label: qx.locale.Manager.tr("All") + " " + resourceAlias,
        icon: "@FontAwesome5Solid/home/20"
      }, {
        id: "my-resources",
        label: qx.locale.Manager.tr("My") + " " + resourceAlias,
        icon: "@FontAwesome5Solid/user/20"
      }, {
        id: "shared-with-me",
        label: qx.locale.Manager.tr("Shared with Me"),
        icon: "@FontAwesome5Solid/users/20"
      }, {
        id: "shared-with-everyone",
        label: qx.locale.Manager.tr("Public") + " " + resourceAlias,
        icon: "@FontAwesome5Solid/globe/20"
      }];
    },

    createChip: function(chipType, chipId, chipLabel) {
      const chipButton = new qx.ui.form.Button().set({
        label: osparc.utils.Utils.capitalize(chipType) + " = '" + chipLabel + "'",
        icon: "@MaterialIcons/close/12",
        toolTipText: chipLabel,
        appearance: "chip-button"
      });
      chipButton.type = chipType;
      chipButton.id = chipId;
      return chipButton;
    },
  },

  events: {
    "filterChanged": "qx.event.type.Data",
    "changeSharedWith": "qx.event.type.Data",
    "changeSelectedTags": "qx.event.type.Data",
    "changeAppType": "qx.event.type.Data",
    "resetButtonPressed": "qx.event.type.Event",
  },

  members: {
    __resourceType: null,
    __currentFilter: null,
    __filtersMenu: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "search-icon":
          control = new qx.ui.basic.Image("@FontAwesome5Solid/search/16").set({
            backgroundColor: "transparent",
            alignY: "middle",
            paddingLeft: 6,
            opacity: 0.5
          });
          this._add(control);
          break;
        case "active-filter-chips":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(4));
          this._add(control);
          break;
        case "text-field":
          control = new qx.ui.form.TextField().set({
            backgroundColor: this.self().BG_COLOR,
            font: "text-16",
            placeholder: this.tr("search"),
            alignY: "bottom",
            marginBottom: 4
          });
          control.getContentElement().setStyles({
            "border-bottom": "none"
          });
          control.addListener("tap", () => this.__showFilterMenu(), this);
          control.addListener("deactivate", () => this.__hideFilterMenu(), this);
          control.addListener("keypress", e => {
            if (e.getKeyIdentifier() === "Enter") {
              this.__filter();
            } else {
              this.__hideFilterMenu();
            }
          }, this);
          control.addListener("focusout", () => this.__filter(), this);
          this._add(control, {
            flex: 1
          });
          osparc.utils.Utils.disableAutocomplete(control);
          break;
        case "reset-button":
          control = new qx.ui.toolbar.Button(null, "@MaterialIcons/close/20").set({
            cursor: "pointer",
            paddingLeft: 0,
            paddingRight: 10,
            alignY: "middle",
            opacity: 0.7
          });
          control.addListener("execute", () => this.resetButtonPressed(), this);
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("search-icon");
      this.getChildControl("active-filter-chips");
      this.getChildControl("text-field");
      this.getChildControl("reset-button");
    },

    __applyActiveFilters: function(filterData) {
      const activeFilterChips = this.getChildControl("active-filter-chips");

      // first remove those that are not active anymore
      this.resetFilters();

      // then add those that are new
      if (filterData["sharedWith"]) {
        const chipFound = activeFilterChips.getChildren().find(chip => chip.type === "shared-with" && chip.id === filterData["sharedWith"]["id"]);
        if (!chipFound) {
          const option = this.self().getSharedWithOptions(this.__resourceType).find(opt => opt.id === filterData["sharedWith"]["id"]);
          this.__addChip("shared-with", filterData["sharedWith"]["id"], option ? option.label : filterData["sharedWith"]["id"]);
        }
      }
      if (filterData["tags"]) {
        filterData["tags"]["id"].forEach(tagId => {
          const chipFound = activeFilterChips.getChildren().find(chip => chip.type === "tag" && chip.id === tagId);
          if (!chipFound) {
            const tag = osparc.store.Tags.getInstance().getTag(tagId);
            this.__addChip("tag", tagId, tag.getName());
          }
        });
      }
      if (filterData["appType"]) {
        const chipFound = activeFilterChips.getChildren().find(chip => chip.type === "app-type" && chip.id === filterData["appType"]["id"]);
        if (!chipFound) {
          const serviceTypes = osparc.service.Utils.TYPES;
          const appTypeInfo = serviceTypes[filterData["appType"]["id"]];
          const label = appTypeInfo ? appTypeInfo.label : filterData["appType"]["id"];
          this.__addChip("app-type", filterData["appType"]["id"], label);
        }
      }
      if (filterData["text"]) {
        this.getChildControl("text-field").setValue(filterData["text"]);
      }
      this.__filter();
    },

    __buildFiltersMenu: function() {
      if (this.__filtersMenu === null) {
        this.__filtersMenu = new qx.ui.menu.Menu();
      }
      const menu = this.__filtersMenu;
      menu.removeAll();

      const sharedWithButton = new qx.ui.menu.Button(this.tr("Shared with"), "@FontAwesome5Solid/share-alt/12");
      this.__addSharedWith(sharedWithButton);
      menu.add(sharedWithButton);

      if (["study", "template"].includes(this.__resourceType)) {
        const tagsButton = new qx.ui.menu.Button(this.tr("Tags"), "@FontAwesome5Solid/tags/12");
        osparc.utils.Utils.setIdToWidget(tagsButton, "searchBarFilter-tags-button");
        this.__addTags(tagsButton);
        menu.add(tagsButton);
      }

      if (this.__resourceType === "service") {
        const appTypeButton = new qx.ui.menu.Button(this.tr("App Type"), "@FontAwesome5Solid/cogs/12");
        this.__addAppTypes(appTypeButton);
        menu.add(appTypeButton);
      }
    },

    getTextFilterValue: function() {
      return this.getChildControl("text-field").getValue() ? this.getChildControl("text-field").getValue().trim() : null;
    },

    __showFilterMenu: function() {
      if (this.getTextFilterValue()) {
        return;
      }

      const textField = this.getChildControl("text-field");
      const element = textField.getContentElement().getDomElement();
      const {
        top,
        left
      } = qx.bom.element.Location.get(element);
      this.__filtersMenu.setLayoutProperties({
        top: top + 30,
        left: left
      });

      if (this.getShowFilterMenu()) {
        this.__filtersMenu.show();
      }
    },

    __hideFilterMenu: function() {
      this.__filtersMenu.exclude();
    },

    __addTags: function(menuButton) {
      const tags = osparc.store.Tags.getInstance().getTags();
      menuButton.setVisibility(tags.length ? "visible" : "excluded");
      if (tags.length) {
        const tagsMenu = new qx.ui.menu.Menu();
        osparc.utils.Utils.setIdToWidget(tagsMenu, "searchBarFilter-tags-menu");
        tags.forEach(tag => {
          const tagButton = new qx.ui.menu.Button(tag.getName(), "@FontAwesome5Solid/tag/12");
          tagButton.getChildControl("icon").setTextColor(tag.getColor());
          tagsMenu.add(tagButton);
          tagButton.addListener("execute", () => {
            this.__addTagToFilterData(tag.getTagId());
          }, this);
        });
        menuButton.setMenu(tagsMenu);
      }
    },

    __addSharedWith: function(menuButton) {
      const options = this.self().getSharedWithOptions(this.__resourceType);
      const sharedWithMenu = new qx.ui.menu.Menu();
      const sharedWithRadioGroup = new qx.ui.form.RadioGroup();
      options.forEach((option, idx) => {
        const button = new qx.ui.menu.RadioButton(option.label);
        sharedWithMenu.add(button);
        button.addListener("execute", () => {
          this.__setSharedWithFilterData(option.id, option.label);
        }, this);
        sharedWithRadioGroup.add(button);
        // preselect show-all
        if (idx === 0) {
          sharedWithRadioGroup.setSelection([button]);
        }
      });
      menuButton.setMenu(sharedWithMenu);
    },

    __addAppTypes: function(menuButton) {
      const serviceTypeMenu = new qx.ui.menu.Menu();
      menuButton.setMenu(serviceTypeMenu);

      const iconSize = 14;
      const serviceTypes = osparc.service.Utils.TYPES;
      Object.keys(serviceTypes).forEach(serviceId => {
        if (!["computational", "dynamic"].includes(serviceId)) {
          return;
        }
        const serviceType = serviceTypes[serviceId];
        const serviceTypeButton = new qx.ui.menu.Button(serviceType.label, serviceType.icon+iconSize);
        serviceTypeButton.getChildControl("icon").set({
          alignX: "center",
        });
        serviceTypeMenu.add(serviceTypeButton);
        serviceTypeButton.addListener("execute", () => {
          this.__setAppTypeFilterData(serviceId, serviceType.label);
        }, this);
      });

      // hypertools filter
      const hypertoolTypeButton = new qx.ui.menu.Button("Hypertools", null);
      hypertoolTypeButton.exclude();
      osparc.store.Templates.getHypertools()
        .then(hypertools => {
          hypertoolTypeButton.setVisibility(hypertools.length > 0 ? "visible" : "excluded");
        });
      osparc.utils.Utils.replaceIconWithThumbnail(hypertoolTypeButton, osparc.data.model.StudyUI.HYPERTOOL_ICON, 18);
      serviceTypeMenu.add(hypertoolTypeButton);
      hypertoolTypeButton.addListener("execute", () => {
        this.__setAppTypeFilterData("hypertool", "Hypertools");
      }, this);
    },

    __setSharedWithFilterData: function(optionId, optionLabel) {
      if (optionId) {
        this.fireDataEvent("changeSharedWith", {
          id: optionId,
          label: optionLabel
        });
      } else {
        this.fireDataEvent("changeSharedWith", null);
      }
    },

    __addTagToFilterData: function(tagId) {
      const selectedTagIds = this.getActiveFilters()["tags"] ? this.getActiveFilters()["tags"]["id"] : [];
      selectedTagIds.push(tagId);
      this.fireDataEvent("changeSelectedTags", selectedTagIds);
    },

    __removeTagFromFilterData: function(tagId) {
      const selectedTagIds = this.getActiveFilters()["tags"] ? this.getActiveFilters()["tags"]["id"] : [];
      const newSelectedTagIds = selectedTagIds.filter(id => id !== tagId);
      this.fireDataEvent("changeSelectedTags", newSelectedTagIds);
    },

    __setAppTypeFilterData: function(appTypeId, appTypeLabel) {
      if (appTypeId) {
        this.fireDataEvent("changeAppType", {
          id: appTypeId,
          label: appTypeLabel
        });
      } else {
        this.fireDataEvent("changeAppType", null);
      }
    },

    /* Used by the StudyBrowser forwarding from the SearchBarFilterExtended. */
    addTagActiveFilter: function(tag) {
      this.__addTagToFilterData(tag.getTagId());
    },

    setSharedWithActiveFilter: function(optionId, optionLabel) {
      this.__setSharedWithFilterData(optionId, optionLabel);
    },
    /* Used by the StudyBrowser forwarding from the SearchBarFilterExtended. */

    // this widget pops up a larger widget with all filters visible
    // and lets users search between projects, templates, public projects and, eventually, files
    popUpSearchBarFilter: function() {
      const initFilterData = this.getFilterData();
      const searchBarFilterExtended = new osparc.dashboard.SearchBarFilterExtended(this.__resourceType, initFilterData);
      const bounds = osparc.utils.Utils.getBounds(this);
      searchBarFilterExtended.setLayoutProperties({
        left: bounds.left,
        top: bounds.top,
      });
      searchBarFilterExtended.set({
        width: bounds.width,
      });
      searchBarFilterExtended.addListener("resetButtonPressed", () => {
        this.resetButtonPressed();
      }, this);
      return searchBarFilterExtended;
    },

    __addChip: function(type, id, label) {
      const activeFilter = this.getChildControl("active-filter-chips");
      const chipFound = activeFilter.getChildren().find(chip => chip.type === type && chip.id === id);
      if (chipFound) {
        return;
      }
      const chip = this.self().createChip(type, id, label);
      chip.addListener("execute", () => {
        // when a chip is removed, we need to update the filters accordingly
        switch (type) {
          case "shared-with":
            this.__setSharedWithFilterData(null, null);
            break;
          case "tag":
            this.__removeTagFromFilterData(id);
            break;
          case "app-type":
            this.__setAppTypeFilterData(null, null);
            break;
        }
      }, this);
      activeFilter.add(chip);
    },

    __removeChips: function() {
      const activeFilter = this.getChildControl("active-filter-chips");
      activeFilter.removeAll();
    },

    resetFilters: function() {
      this.__removeChips();
      this.getChildControl("text-field").resetValue();
    },

    resetButtonPressed: function() {
      this.resetFilters();
      this._filterChange(this.self().getInitialFilterData());
      this.fireEvent("resetButtonPressed");
    },

    getFilterData: function() {
      const filterData = this.self().getInitialFilterData();
      const textFilter = this.getTextFilterValue();
      filterData["text"] = textFilter ? textFilter : "";
      this.getChildControl("active-filter-chips").getChildren().forEach(chip => {
        switch (chip.type) {
          case "tag":
            filterData.tags.push(chip.id);
            break;
          case "shared-with":
            filterData.sharedWith = chip.id === "show-all" ? null : chip.id;
            break;
          case "app-type":
            filterData.appType = chip.id;
            break;
        }
      });
      return filterData;
    },

    __filter: function() {
      const filterData = this.getFilterData();
      // if text is shorter than 3 chars, ignore
      if (filterData["text"].length > 0 && filterData["text"].length < 3) {
        osparc.FlashMessenger.logAs(this.tr("Please enter at least 3 characters to search."), "INFO");
        return;
      }
      if (JSON.stringify(this.__currentFilter) !== JSON.stringify(filterData)) {
        this.__currentFilter = filterData;
        this.fireDataEvent("filterChanged", filterData);
        this._filterChange(filterData);
      }
    }
  }
});
