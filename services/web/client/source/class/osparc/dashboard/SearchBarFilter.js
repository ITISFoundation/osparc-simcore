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
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(5));

    this.set({
      backgroundColor: "background-main-lighter+",
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
    FilterGroupId: "searchBarFilter"
  },

  members: {
    __activeFilters: null,
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
            backgroundColor: "background-main-lighter+",
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
      const menu = this.__filtersMenu = new qx.ui.menu.Menu();
      const tagsButton = new qx.ui.menu.Button("Tags");
      this.__addTags(tagsButton);
      menu.add(tagsButton);

      const classifiersButton = new qx.ui.menu.Button("Classifiers");
      this.__addClassifiers(classifiersButton);
      menu.add(classifiersButton);
    },

    __attachEventHandlers: function() {
      const textField = this.getChildControl("text-field");
      textField.addListener("tap", () => this.__showFilterMenu(), this);
      textField.addListener("deactivate", () => this.__hideFilterMenu(), this);

      const resetButton = this.getChildControl("reset-button");
      resetButton.addListener("execute", () => this.__resetFilters(), this);
    },

    __showFilterMenu: function() {
      const element = this.getChildControl("text-field").getContentElement().getDomElement();
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
        tags.forEach(tag => {
          const tagButton = new qx.ui.menu.Button(tag.name);
          tagsMenu.add(tagButton);
          tagButton.addListener("execute", () => this.__addChip("tag", tag.name, tag.name), this);
        });
        menuButton.setMenu(tagsMenu);
      }
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

    __createChip: function(chipType, chipId, chipLabel) {
      const chipButton = new qx.ui.form.Button().set({
        label: osparc.utils.Utils.capitalize(chipType) + " = '" + chipLabel + "'",
        icon: "@MaterialIcons/close/12",
        iconPosition: "right",
        paddingRight: 4,
        paddingLeft: 4,
        alignY: "middle",
        toolTipText: chipLabel,
        maxHeight: 26,
        maxWidth: 180
      });
      chipButton.type = chipType;
      chipButton.id = chipId;
      chipButton.getContentElement().setStyles({
        "border-radius": "4px"
      });
      chipButton.addListener("execute", () => this.__removeChip(chipType, chipId), this);
      return chipButton;
    },

    __addChip: function(type, id, label) {
      const activeFilter = this.getChildControl("active-filters");
      const chipFound = activeFilter.getChildren().find(chip => chip.type === type && chip.id === id);
      if (chipFound) {
        return;
      }
      const chip = this.__createChip(type, id, label);
      this.getChildControl("active-filters").add(chip);
    },

    __removeChip: function(type, id) {
      const activeFilter = this.getChildControl("active-filters");
      const chipFound = activeFilter.getChildren().find(chip => chip.type === type && chip.id === id);
      if (chipFound) {
        activeFilter.remove(chipFound);
      }
    },

    __resetFilters: function() {
      this.getChildControl("active-filters").removeAll();
      this.getChildControl("text-field").resetValue();
    }
  }
});
