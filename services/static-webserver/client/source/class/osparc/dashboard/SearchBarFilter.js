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

    this.__attachEventHandlers();

    this.__currentFilter = null;
  },

  properties: {
    showFilterMenu: {
      check: "Boolean",
      init: true,
      event: "changeShowFilterMenu",
    }
  },

  statics: {
    HEIGHT: 36,
    BG_COLOR: "input_background",

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
    "filterChanged": "qx.event.type.Data"
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
        case "active-filters":
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
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("search-icon");
      this.getChildControl("active-filters");
      this.getChildControl("text-field");
      this.getChildControl("reset-button");
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

        const classifiersButton = new qx.ui.menu.Button(this.tr("Classifiers"), "@FontAwesome5Solid/search/12");
        this.__addClassifiers(classifiersButton);
        menu.add(classifiersButton);
      }

      if (this.__resourceType === "service") {
        const appTypeButton = new qx.ui.menu.Button(this.tr("App Type"), "@FontAwesome5Solid/cogs/12");
        this.__addAppTypes(appTypeButton);
        menu.add(appTypeButton);
      }
    },

    __attachEventHandlers: function() {
      const textField = this.getChildControl("text-field");
      textField.addListener("tap", () => this.__showFilterMenu(), this);
      textField.addListener("deactivate", () => this.__hideFilterMenu(), this);
      textField.addListener("keypress", e => {
        if (e.getKeyIdentifier() === "Enter") {
          this.__filter();
        } else {
          this.__hideFilterMenu();
        }
      }, this);
      textField.addListener("focusout", () => this.__filter(), this);

      const resetButton = this.getChildControl("reset-button");
      resetButton.addListener("execute", () => this.__resetFilters(), this);

      osparc.store.Store.getInstance().addListener("changeTags", () => this.__buildFiltersMenu(), this);
    },

    getTextFilterValue: function() {
      return this.getChildControl("text-field").getValue();
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
          tagButton.addListener("execute", () => this.addTagActiveFilter(tag), this);
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
        button.addListener("execute", () => this.setSharedWithActiveFilter(option.id, option.label), this);
        sharedWithRadioGroup.add(button);
        // preselect show-all
        if (idx === 0) {
          sharedWithRadioGroup.setSelection([button]);
        }
      });
      menuButton.setMenu(sharedWithMenu);
    },

    __addClassifiers: function(menuButton) {
      const classifiers = osparc.store.Store.getInstance().getClassifiers();
      menuButton.setVisibility(classifiers && classifiers.length ? "visible" : "excluded");
      if (classifiers && classifiers.length) {
        const classifiersMenu = new qx.ui.menu.Menu();
        classifiers.forEach(classifier => {
          const classifierButton = new qx.ui.menu.Button(classifier.display_name);
          classifiersMenu.add(classifierButton);
          classifierButton.addListener("execute", () => this.__addChip("classifier", classifier.classifier, classifier.display_name), this);
        });
        menuButton.setMenu(classifiersMenu);
      }
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
        serviceTypeButton.addListener("execute", () => this.__addChip("app-type", serviceId, serviceType.label), this);
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
      hypertoolTypeButton.addListener("execute", () => this.__addChip("app-type", "hypertool", "Hypertools"), this);
    },

    addTagActiveFilter: function(tag) {
      this.__addChip("tag", tag.getTagId(), tag.getName());
    },

    setTagsActiveFilter: function(tagIds) {
      const tags = osparc.store.Tags.getInstance().getTags();
      tags.forEach(tag => {
        const tagId = tag.getTagId();
        if (tagIds.includes(tagId)) {
          this.__addChip("tag", tagId, tag.getName());
        } else {
          this.__removeChip("tag", tagId, tag.getName());
        }
      });
    },

    setSharedWithActiveFilter: function(optionId, optionLabel) {
      this.__removeChips("shared-with");
      if (optionId === "show-all") {
        this.__filter();
      } else {
        this.__addChip("shared-with", optionId, optionLabel);
      }
    },

    setAppTypeActiveFilter: function(appType, optionLabel) {
      this.__removeChips("app-type");
      if (appType && optionLabel) {
        this.__addChip("app-type", appType, optionLabel);
      } else {
        this.__filter();
      }
    },

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
      return searchBarFilterExtended;
    },

    __addChip: function(type, id, label) {
      const activeFilter = this.getChildControl("active-filters");
      const chipFound = activeFilter.getChildren().find(chip => chip.type === type && chip.id === id);
      if (chipFound) {
        return;
      }
      const chip = this.self().createChip(type, id, label);
      chip.addListener("execute", () => this.__removeChip(chipType, chipId), this);
      activeFilter.add(chip);
      this.__filter();
    },

    __removeChip: function(type, id) {
      const activeFilter = this.getChildControl("active-filters");
      const chipFound = activeFilter.getChildren().find(chip => chip.type === type && chip.id === id);
      if (chipFound) {
        activeFilter.remove(chipFound);
        this.__filter();
      }
    },

    __removeChips: function(type) {
      const activeFilter = this.getChildControl("active-filters");
      if (type) {
        const chipsFounds = activeFilter.getChildren().filter(chip => chip.type === type);
        for (let i=chipsFounds.length-1; i>=0; i--) {
          activeFilter.remove(chipsFounds[i]);
        }
      } else {
        activeFilter.removeAll();
      }
    },

    resetFilters: function() {
      this.__removeChips();
      this.getChildControl("text-field").resetValue();
    },

    __resetFilters: function() {
      this.resetFilters();
      this.__filter();
    },

    getFilterData: function() {
      const filterData = {
        tags: [],
        classifiers: [],
        sharedWith: null,
        appType: null,
        text: ""
      };
      const textFilter = this.getTextFilterValue();
      filterData["text"] = textFilter ? textFilter : "";
      this.getChildControl("active-filters").getChildren().forEach(chip => {
        switch (chip.type) {
          case "tag":
            filterData.tags.push(chip.id);
            break;
          case "classifier":
            filterData.classifiers.push(chip.id);
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
      if (JSON.stringify(this.__currentFilter) !== JSON.stringify(filterData)) {
        this.__currentFilter = filterData;
        this.fireDataEvent("filterChanged", filterData);
        this._filterChange(filterData);
      }
    }
  }
});
