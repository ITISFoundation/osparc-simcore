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

  construct: function() {
    this.base(arguments);

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
      event: "changeSharedWith",
      apply: "__applySharedWith"
    }
  },

  members: {
    __applyFilterBy: function(filterBy) {
      console.log("filterBy", filterBy);
    },

    __buildLayout: function() {
      this.__buildSharedWithFilter();
    },

    __buildSharedWithFilter: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      const radioGroup = new qx.ui.form.RadioGroup();

      const options = osparc.dashboard.SearchBarFilter.getSharedWithOptions("study");
      options.forEach(option => {
        const button = new qx.ui.toolbar.RadioButton(option.label, option.icon);
        button.id = option.id;
        button.set({
          font: "text-14",
          gap: 6,
          backgroundColor: "transparent",
          padding: 8
        });
        button.getChildControl("icon").set({
          width: 25, // align all icons
          scale: true
        })
        button.getContentElement().setStyles({
          "border-radius": "8px"
        });

        layout.add(button);
        radioGroup.add(button);

        button.addListener("execute", () => this.setSharedWith(option.id), this);
      });

      radioGroup.setAllowEmptySelection(false);

      this._add(layout);
    }
  }
});
