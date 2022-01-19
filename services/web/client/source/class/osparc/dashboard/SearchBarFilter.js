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
      maxHeight: 30
    });

    this.__buildLayout();

    this.__attachEventHandlers();
  },

  properties: {
    appearance: {
      init: "dashboard",
      refine: true
    }
  },

  statics: {
    FilterGroupId: "searchBarFilter"
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "tags-filter": {
          control = new osparc.component.filter.UserTagsFilter("tags", this.self().FilterGroupId).set({
            printTags: false
          });
          this._add(control);
          break;
        }
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
            font: "text-16",
            placeholder: this.tr("search"),
            alignY: "bottom"
          });
          this._add(control, {
            flex: 1
          });
          break;
        case "reset-button":
          control = new qx.ui.toolbar.Button(null, "@MaterialIcons/close/12").set({
            backgroundColor: "transparent",
            paddingLeft: 0,
            alignY: "middle",
            opacity: 0.7
          });
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("tags-filter");
      this.getChildControl("search-icon");
      this.getChildControl("active-filters");

      // const filterGroupId = "searchBarFilter";
      const textField = this.getChildControl("text-field");
      textField.addListener("changeValue", () => this.__filter(), this);

      const resetButton = this.getChildControl("reset-button");
      resetButton.addListener("execute", () => this.__resetFilters(), this);
    },

    __attachEventHandlers: function() {
      const tagsFilter = this.getChildControl("tags-filter");
      tagsFilter.addListener("activeTagsChanged", () => this.__reloadChips(), this);

      const textField = this.getChildControl("text-field");
      textField.addListener("changeValue", () => this.__filter(), this);

      const resetButton = this.getChildControl("reset-button");
      resetButton.addListener("execute", () => this.__resetFilters(), this);
    },

    __reloadChips: function() {
      const activeFilters = this.getChildControl("active-filters");
      activeFilters.removeAll();
      this.getChildControl("tags-filter").getActiveTags().forEach(tagName => {
        const tagButton = this.__createChip("tag", tagName);
        activeFilters.add(tagButton);
      });
    },

    __createChip: function(chipType, chipLabel) {
      const chipButton = new qx.ui.toolbar.Button().set({
        label: chipType + ":'" + chipLabel + "'",
        icon: "@MaterialIcons/close/14"
      });
      chipButton.addListener("execute", () => this.__removeChip(chipType, chipLabel), this);
    },

    __removeChip: function(chipType, chipLabel) {
      switch (chipType) {
        case "tag": {
          const tagsFilter = this.getChildControl("tags-filter");
          tagsFilter.removeTag(chipLabel);
          break;
        }
      }
    },

    __resetFilters: function() {
      this.getChildControl("text-field").resetValue();
    },

    __filter: function() {
      console.log(this.getChildControl("text-field").getValue());
    }
  }
});
