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

    this.setLayout(new qx.ui.layout.VBox(10));
    this.set({
      padding: 10
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

      const showAll = new qx.ui.toolbar.RadioButton("Home", "@FontAwesome5Solid/home/20");
      showAll.filterById = "show-all";
      layout.add(showAll);

      const myStudies = new qx.ui.toolbar.RadioButton("My Studies", "@FontAwesome5Solid/user/20");
      myStudies.filterById = "my-resources";
      layout.add(myStudies);

      const sharedWithMe = new qx.ui.toolbar.RadioButton("Shared with me", "@FontAwesome5Solid/users/20");
      sharedWithMe.filterById = "shared-with-me";
      layout.add(sharedWithMe);

      const sharedWithEveryone = new qx.ui.toolbar.RadioButton("Shared with Everyone", "@FontAwesome5Solid/globe/20");
      sharedWithEveryone.filterById = "shared-with-everyone";
      layout.add(sharedWithEveryone);

      const radioGroup = new qx.ui.form.RadioGroup();
      radioGroup.add(showAll);
      radioGroup.add(myStudies);
      radioGroup.add(sharedWithMe);
      radioGroup.add(sharedWithEveryone);
      radioGroup.setAllowEmptySelection(false);

      this._add(layout);
    }
  }
});
