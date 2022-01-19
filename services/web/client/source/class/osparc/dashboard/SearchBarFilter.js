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

    this._setLayout(new qx.ui.layout.HBox());

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
            paddingRight: 6,
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

      const clasButton = new qx.ui.menu.Button("Classifiers", null, null, this.__getClassifiers());
      menu.add(clasButton);
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
          tagButton.tag = tag;
          tagsMenu.add(tagButton);
          tagButton.addListener("execute", () => {
            const tagChip = this.__createChip("tag", tag.name);
            this.getChildControl("active-filters").add(tagChip);
          }, this);
        });
        menuButton.setMenu(tagsMenu);
      }
    },

    __getClassifiers: function() {
      const clasMenu = new qx.ui.menu.Menu();
      [
        "Clas1",
        "Clas2"
      ].forEach(clas => {
        const clasButton = new qx.ui.menu.Button(clas);
        clasMenu.add(clasButton);
      });
      return clasMenu;
    },

    __createChip: function(chipType, chipLabel) {
      const chipButton = new qx.ui.toolbar.Button().set({
        label: osparc.utils.Utils.capitalize(chipType) + " = '" + chipLabel + "'",
        icon: "@MaterialIcons/close/12",
        iconPosition: "right",
        paddingRight: 4,
        paddingLeft: 4
      });
      chipButton.type = chipType;
      chipButton.label = chipLabel;
      chipButton.getContentElement().setStyles({
        "border-radius": "4px"
      });
      chipButton.addListener("execute", () => this.__removeChip(chipType, chipLabel), this);
      return chipButton;
    },

    __removeChip: function(chipType, chipLabel) {
      const activeFilter = this.getChildControl("active-filters");
      const chipFound = activeFilter.getChildren().find(chip => chip.type === chipType && chip.label === chipLabel);
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
