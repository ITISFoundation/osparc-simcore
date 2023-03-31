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
  extend: osparc.component.filter.UIFilter,

  construct: function(resourceType) {
    this.__resourceType = resourceType;

    this.base(arguments, "searchBarFilter-"+resourceType, "searchBarFilter");

    this._setLayout(new qx.ui.layout.HBox(5));

    this.set({
      backgroundColor: "background-main-2",
      paddingLeft: 6,
      height: 36
    });
    this.getContentElement().setStyles({
      "border-radius": "8px"
    });

    this.__buildLayout();

    this.__buildFiltersMenu();

    this.__attachEventHandlers();
  },

  statics: {
    getSharedWithOptions: function(resourceType) {
      return [{
        id: "show-all",
        label: qx.locale.Manager.tr("Show all")
      }, {
        id: "my-studies",
        label: qx.locale.Manager.tr("My ") + osparc.utils.Utils.resourceTypeToAlias(resourceType, {
          plural: true
        })
      }, {
        id: "shared-with-me",
        label: qx.locale.Manager.tr("Shared with me")
      }];
    }
  },

  members: {
    __resourceType: null,
    __filtersMenu: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "search-icon":
          control = new qx.ui.basic.Image("@FontAwesome5Solid/search/16").set({
            backgroundColor: "transparent",
            alignY: "middle",
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
            backgroundColor: "background-main-2",
            font: "text-16",
            placeholder: this.tr("search"),
            alignY: "bottom",
            marginBottom: 4
          });
          this._add(control, {
            flex: 1
          });
          break;
        case "reset-button":
          control = new qx.ui.toolbar.Button(null, "@MaterialIcons/close/12").set({
            backgroundColor: "transparent",
            paddingLeft: 0,
            paddingRight: 0,
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
      const tagsButton = new qx.ui.menu.Button(this.tr("Tags"), "@FontAwesome5Solid/tags/12");
      osparc.utils.Utils.setIdToWidget(tagsButton, "searchBarFilter-tags-button");
      this.__addTags(tagsButton);
      menu.add(tagsButton);

      const sharedWithButton = new qx.ui.menu.Button(this.tr("Shared with"), "@FontAwesome5Solid/share-alt/12");
      this.__addSharedWith(sharedWithButton);
      menu.add(sharedWithButton);

      const classifiersButton = new qx.ui.menu.Button(this.tr("Classifiers"), "@FontAwesome5Solid/search/12");
      osparc.utils.Utils.setIdToWidget(classifiersButton, "searchBarFilter-classifiers");
      this.__addClassifiers(classifiersButton);
      menu.add(classifiersButton);
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
      textField.addListener("changeValue", () => this.__filter(), this);

      const resetButton = this.getChildControl("reset-button");
      resetButton.addListener("execute", () => this.__resetFilters(), this);

      osparc.store.Store.getInstance().addListener("changeTags", () => this.__buildFiltersMenu(), this);
    },

    __showFilterMenu: function() {
      const textField = this.getChildControl("text-field");
      const textValue = textField.getValue();
      if (textValue) {
        return;
      }

      const element = textField.getContentElement().getDomElement();
      const {
        top,
        left
      } = qx.bom.element.Location.get(element);
      this.__filtersMenu.setLayoutProperties({
        top: top + 30,
        left: left
      });

      this.__filtersMenu.show();
    },

    __hideFilterMenu: function() {
      this.__filtersMenu.exclude();
    },

    __addTags: function(menuButton) {
      const tags = osparc.store.Store.getInstance().getTags();
      menuButton.setVisibility(tags.length ? "visible" : "excluded");
      if (tags.length) {
        const tagsMenu = new qx.ui.menu.Menu();
        osparc.utils.Utils.setIdToWidget(tagsMenu, "searchBarFilter-tags-menu");
        tags.forEach(tag => {
          const tagButton = new qx.ui.menu.Button(tag.name, "@FontAwesome5Solid/tag/12");
          tagButton.getChildControl("icon").setTextColor(tag.color);
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
        const sharedWithButton = new qx.ui.menu.RadioButton(option.label);
        sharedWithMenu.add(sharedWithButton);
        sharedWithButton.addListener("execute", () => {
          this.__removeChips("shared-with");
          if (option.id === "show-all") {
            this.__filter();
          } else {
            this.__addChip("shared-with", option.id, option.label);
          }
        }, this);
        sharedWithRadioGroup.add(sharedWithButton);
        // preselect show-all
        if (idx === 0) {
          sharedWithRadioGroup.setSelection([sharedWithButton]);
        }
      });
      menuButton.setMenu(sharedWithMenu);
    },

    __addClassifiers: function(menuButton) {
      const classifiers = osparc.store.Store.getInstance().getClassifiers();
      menuButton.setVisibility(classifiers.length ? "visible" : "excluded");
      if (classifiers.length) {
        const classifiersMenu = new qx.ui.menu.Menu();
        classifiers.forEach(classifier => {
          const classifierButton = new qx.ui.menu.Button(classifier.display_name);
          classifiersMenu.add(classifierButton);
          classifierButton.addListener("execute", () => this.__addChip("classifier", classifier.classifier, classifier.display_name), this);
        });
        menuButton.setMenu(classifiersMenu);
      }
    },

    addTagActiveFilter: function(tag) {
      this.__addChip("tag", tag.name, tag.name);
    },

    __addChip: function(type, id, label) {
      const activeFilter = this.getChildControl("active-filters");
      const chipFound = activeFilter.getChildren().find(chip => chip.type === type && chip.id === id);
      if (chipFound) {
        return;
      }
      const chip = this.__createChip(type, id, label);
      activeFilter.add(chip);
      this.__filter();
    },

    __createChip: function(chipType, chipId, chipLabel) {
      const chipButton = new qx.ui.form.Button().set({
        label: osparc.utils.Utils.capitalize(chipType) + " = '" + chipLabel + "'",
        icon: "@MaterialIcons/close/12",
        iconPosition: "right",
        paddingRight: 6,
        paddingLeft: 6,
        alignY: "middle",
        toolTipText: chipLabel,
        maxHeight: 26,
        maxWidth: 200,
        backgroundColor: "background-main-1"
      });
      chipButton.type = chipType;
      chipButton.id = chipId;
      chipButton.getContentElement().setStyles({
        "border-radius": "6px"
      });
      chipButton.addListener("execute", () => this.__removeChip(chipType, chipId), this);
      return chipButton;
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

    __resetFilters: function() {
      this.__removeChips();
      this.getChildControl("text-field").resetValue();
      this.__filter();
    },

    __filter: function() {
      const filterData = {
        tags: [],
        classifiers: [],
        sharedWith: null,
        text: this.getChildControl("text-field").getValue() ? this.getChildControl("text-field").getValue() : ""
      };
      this.getChildControl("active-filters").getChildren().forEach(chip => {
        switch (chip.type) {
          case "tag":
            filterData.tags.push(chip.id);
            break;
          case "shared-with":
            if (chip.id === "show-all") {
              filterData.sharedWith = null;
            } else {
              filterData.sharedWith = chip.id;
            }
            break;
          case "classifier":
            filterData.classifiers.push(chip.id);
            break;
        }
      });
      this._filterChange(filterData);
    }
  }
});
