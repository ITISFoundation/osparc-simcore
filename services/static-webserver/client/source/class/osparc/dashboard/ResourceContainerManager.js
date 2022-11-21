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

qx.Class.define("osparc.dashboard.ResourceContainerManager", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments, new qx.ui.layout.VBox(10));

    this.__flatList = new osparc.dashboard.ToggleButtonContainer();
    this.__groupedLists = [];
  },

  properties: {
    mode: {
      check: ["grid", "list"],
      init: "grid",
      nullable: false,
      event: "changeMode",
      apply: "__applyMode"
    },

    groupBy: {
      check: [null, "tags"],
      init: null,
      nullable: true,
      apply: "__applyGroupBy"
    }
  },

  events: {
    "changeSelection": "qx.event.type.Data",
    "changeVisibility": "qx.event.type.Data"
  },

  members: {
    __flatList: null,
    __groupedLists: null,

    getContainer: function() {
      return this.__flatList;
    },

    __applyGroupBy: function() {
      const cards = this.getCards();
      this.removeAll();
      const header = this.__emptyHeaders();
      if (this.getGroupBy()) {
        this.add(header);
      }
      cards.forEach(card => this.add(card));
    }
  }
});
