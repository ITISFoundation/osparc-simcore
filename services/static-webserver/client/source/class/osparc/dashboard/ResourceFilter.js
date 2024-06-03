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
    filterBy: {
      check: ["show-all", "my-resources", "shared-with-me", "shared-with-everyone"],
      init: "all",
      nullable: false,
      event: "changeFilterBy",
      apply: "__applyFilterBy"
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
      const buttons = [];

      const showAll = new qx.ui.toolbar.RadioButton("Home", "@FontAwesome5Solid/home/20").set({
        gap: 6
      });
      showAll.filterById = "show-all";
      buttons.push(showAll);

      const myResources = new qx.ui.toolbar.RadioButton("My Studies", "@FontAwesome5Solid/user/20");
      myResources.filterById = "my-resources";
      buttons.push(myResources);

      const sharedWithMe = new qx.ui.toolbar.RadioButton("Shared with me", "@FontAwesome5Solid/users/20");
      sharedWithMe.filterById = "shared-with-me";
      buttons.push(sharedWithMe);

      const sharedWithEveryone = new qx.ui.toolbar.RadioButton("Shared with Everyone", "@FontAwesome5Solid/globe/20");
      sharedWithEveryone.filterById = "shared-with-everyone";
      buttons.push(sharedWithEveryone);

      const radioGroup = new qx.ui.form.RadioGroup();

      buttons.forEach(button => {
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
      });

      radioGroup.setAllowEmptySelection(false);

      this._add(layout);
    }
  }
});
