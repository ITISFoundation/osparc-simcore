/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Julian Querido (jsaq007)

************************************************************************ */

qx.Class.define("osparc.dashboard.SortedByMenuButton", {
  extend: qx.ui.form.MenuButton,

  construct: function() {
    this.base(arguments, this.tr("Sort"), "@FontAwesome5Solid/chevron-down/10");

    osparc.utils.Utils.setIdToWidget(this, "sortedByButton");

    this.set({
      iconPosition: "left",
      marginRight: 8
    });

    const sortedByMenu = new qx.ui.menu.Menu().set({
      font: "text-14"
    });
    this.setMenu(sortedByMenu);

    const options = this.self().getSortByOptions();

    options.forEach((option, idx) => {
      const btn = new qx.ui.menu.Button();
      btn.btnId = option.id;
      btn.set({
        label: option.label,
        icon: null
      });
      // Sort by last modified date
      if (idx === options.length -1) {
        this.__menuButton = btn;
        btn.setIcon("@FontAwesome5Solid/arrow-down/14");
      }
      sortedByMenu.add(btn);

      btn.addListener("execute", () => {
        this.__buttonExecuted(btn)
      });
    });

    this.addListener("changeSortField", e => {
      const sort = {
        field: e.getData(),
        direction: true
      }
      this.__handelSortEvent(sort)
    }, this);

    this.addListener("changeSortDirection", e => {
      const sort = {
        field: this.getSortField(),
        direction: e.getData()
      }
      this.__handelSortEvent(sort)
    }, this);
  },

  statics: {
    DefaultSorting: {
      field: "last_change_date",
      direction: "desc"
    },
    getSortByOptions: function() {
      return [{
        id: "name",
        label: qx.locale.Manager.tr("Name")
      }, {
        id: "prj_owner",
        label: qx.locale.Manager.tr("Owner")
      }, {
        id: "creation_date",
        label: qx.locale.Manager.tr("Created"),
      }, {
        id: "last_change_date",
        label: qx.locale.Manager.tr("Modified"),
      }];
    }
  },

  events: {
    "sortByChanged": "qx.event.type.Data"
  },

  properties: {
    sortField: {
      check: "String",
      init: "last_change_date",
      nullable: true,
      event: "changeSortField",
      apply: "__applySortField"
    },
    sortDirection: {
      check: "Boolean",
      init: true,
      nullable: true,
      event: "changeSortDirection",
      apply: "__applySortDirection"
    }
  },

  members: {
    __menuButton: null,
    __buttonExecuted: function(btn) {
      if (this.__menuButton) {
        this.__menuButton.setIcon(null);
      }
      this.__menuButton = btn;
      this.set({
        label: btn.getLabel(),
        icon: "@FontAwesome5Solid/chevron-down/10"
      });

      const data = {
        "id": btn.btnId,
      };
      this.__handelSort(data.id);
    },

    __handelSort: function(field) {
      if (field === this.getSortField()) {
        const direction = !this.getSortDirection();
        this.setSortDirection(direction)
        return;
      }
      this.setSortField(field)
    },

    __handelSortEvent: function({field, direction}) {
      this.__menuButton.setIcon(direction ? "@FontAwesome5Solid/arrow-down/14" : "@FontAwesome5Solid/arrow-up/14")
      const sort = {
        field: field,
        direction: direction ? "desc" : "asc"
      };
      this.fireDataEvent("sortByChanged", sort);
    },

    __applySortField: function(value, old) {

    },

    __applySortDirection: function(value, old) {

    }
  }
});
