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
    this.__sharedWithButtons = [];
    this.__tagButtons = [];

    this._setLayout(new qx.ui.layout.VBox());
    this.__buildLayout();
  },

  events: {
    "changeSharedWith": "qx.event.type.Data",
    "changeSelectedTags": "qx.event.type.Data"
  },

  members: {
    __resourceType: null,
    __sharedWithButtons: null,
    __tagButtons: null,

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
        const button = new qx.ui.toolbar.RadioButton(option.label, option.icon);
        button.id = option.id;
        button.set({
          appearance: "filter-toggle-button"
        });

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

      radioGroup.setAllowEmptySelection(false);

      return layout;
    },

    __createTagsFilterLayout: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      osparc.store.Store.getInstance().getTags().forEach(tag => {
        const button = new qx.ui.form.ToggleButton(tag.name, "@FontAwesome5Solid/tag/20");
        button.id = tag.id;
        button.set({
          appearance: "filter-toggle-button"
        });
        button.getChildControl("icon").set({
          textColor: tag.color
        });

        layout.add(button);

        button.addListener("execute", () => {
          const selectedTagIds = this.__tagButtons.filter(btn => btn.getValue()).map(btn => btn.id);
          this.fireDataEvent("changeSelectedTags", selectedTagIds);
        }, this);

        this.__tagButtons.push(button);
      });

      return layout;
    },

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
    }
  }
});
