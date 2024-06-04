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

    this._setLayout(new qx.ui.layout.VBox(10));
    this.set({
      padding: 10,
      allowGrowX: false
    });

    this.__buildLayout();
  },

  properties: {
    sharedWith: {
      check: ["show-all", "my-resources", "shared-with-me", "shared-with-everyone"],
      init: "all",
      nullable: false,
      apply: "__applySharedWith"
    }
  },

  events: {
    "changeSharedWith": "qx.event.type.Data"
  },

  members: {
    __resourceType: null,

    __buildLayout: function() {
      this.__buildSharedWithFilter();
    },

    __buildSharedWithFilter: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      const radioGroup = new qx.ui.form.RadioGroup();

      const options = osparc.dashboard.SearchBarFilter.getSharedWithOptions(this.__resourceType);
      options.forEach(option => {
        const button = new qx.ui.toolbar.RadioButton(option.label, option.icon);
        button.id = option.id;
        button.set({
          appearance: "filter-toggle-button",
          gap: 8
        });
        button.getChildControl("icon").set({
          width: 25, // align all icons
          scale: true
        });

        layout.add(button);
        radioGroup.add(button);

        button.addListener("execute", () => this.fireDataEvent("changeSharedWith", {
          id: option.id,
          label: option.label
        }), this);
      });

      radioGroup.setAllowEmptySelection(false);

      this._add(layout);
    },

    __applySharedWith: function(sharedWith) {
      console.log("SharedWith", sharedWith);
    }
  }
});
