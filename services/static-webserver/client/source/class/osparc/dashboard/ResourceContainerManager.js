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

    areMoreResourcesRequired: function() {
      if (this.__flatList) {
        return this.__flatList.areMoreResourcesRequired();
      }
      return false;
    },

    getCards: function() {
      if (this.__flatList) {
        return this.__flatList.getCards();
      }
      const cards = [];
      this.__groupedLists.forEach(groupedList => cards.push(...groupedList.getCards()));
      return cards;
    },

    resetSelection: function() {
      if (this.__flatList) {
        this.__flatList.resetSelection();
      }
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
