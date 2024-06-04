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

    this.__resourceType = resourceType;

    this._setLayout(new qx.ui.layout.VBox());

    this.__buildLayout();
  },

  properties: {
    sharedWith: {
      check: ["show-all", "my-resources", "shared-with-me", "shared-with-everyone"],
      init: "all",
      nullable: false,
      apply: "__applySharedWith"
    },

    selectedTags: {
      check: "Array",
      init: [],
      nullable: false,
      apply: "__applySelectedTags"
    }
  },

  events: {
    "changeSharedWith": "qx.event.type.Data",
    "changeSelectedTags": "qx.event.type.Data"
  },

  members: {
    __resourceType: null,

    __buildLayout: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(40));
      layout.add(this.__createSharedWithFilterLayout());
      layout.add(this.__createTagsFilterLayout());

      const scrollContainer = new qx.ui.container.Scroll();
      scrollContainer.add(layout);
      this._add(scrollContainer, {
        flex: 1
      });
    },

    __createSharedWithFilterLayout: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      const radioGroup = new qx.ui.form.RadioGroup();

      const options = osparc.dashboard.SearchBarFilter.getSharedWithOptions(this.__resourceType);
      options.forEach(option => {
        const button = new qx.ui.toolbar.RadioButton(option.label, option.icon).set({
          appearance: "filter-toggle-button"
        });

        layout.add(button);
        radioGroup.add(button);

        button.addListener("execute", () => this.fireDataEvent("changeSharedWith", {
          id: option.id,
          label: option.label
        }), this);
      });

      radioGroup.setAllowEmptySelection(false);

      return layout;
    },

    __createTagsFilterLayout: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      osparc.store.Store.getInstance().getTags().forEach(tag => {
        const button = new qx.ui.form.ToggleButton(tag.name, "@FontAwesome5Solid/tag/20");
        button.set({
          appearance: "filter-toggle-button",
          gap: 8
        });
        button.getChildControl("icon").set({
          width: 25, // align all icons
          scale: true,
          textColor: tag.color
        });
        layout.add(button);
        button.addListener("execute", () => this.fireDataEvent("changeSelectedTags", {
          id: tag.id,
          label: tag.label
        }), this);
      });

      return layout;
    },

    __applySharedWith: function(sharedWith) {
      console.log("sharedWith", sharedWith);
    },

    __applySelectedTags: function(selectedTags) {
      console.log("selectedTags", selectedTags);
    },

    filterChanged: function(filterData) {
      console.log(filterData);
    }
  }
});
