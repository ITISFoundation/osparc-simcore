/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.dashboard.SortByButtonGroup", {
  extend: qx.ui.core.Widget,

  construct: function(resource = "study") {
    this.base(arguments, this.tr("Sort"), "@FontAwesome5Solid/chevron-down/10");

    osparc.utils.Utils.setIdToWidget(this, "sortedByButton");

    this._setLayout(new qx.ui.layout.HBox(5));

    this.set({
      backgroundColor: "red",
    });

    const buttonContainer = this.__buttonContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
      alignX: "center",
      alignY: "middle",
    }));
    this.__resourceType = resource;
    const options = this.self().getSortByOptions(resource);

    options.forEach((option, idx) => {
      const btn = new qx.ui.form.Button().set({
        appearance: "form-button-outlined",
        alignY: "middle",
      })
      btn.btnId = option.id;
      btn.set({
        label: option.label,
        // icon: option.icon
      });
      this.__buttonContainer.add(btn);

      btn.addListener("execute", () => this.__buttonExecuted(btn), this);
      btn.addListener("changeField", e => {
        const direction = this.getDirection();
        this.__handleSort(e.getData(), direction)
      }, this);
      btn.addListener("changeDirection", e => {
        const field = this.getField();
        this.__handleSort(field, e.getData())
      }, this);

      // Sort by last modified date
      if (idx === options.length) {
        btn.execute();
      }
    });
    this._add(buttonContainer)
  },

  statics: {
    DefaultSorting: {
      field: "last_change_date",
      direction: "desc"
    },
    getSortByOptions: function() {
      return [{
        id: "name",
        label: qx.locale.Manager.tr("Name"),
        // icon: "@FontAwesome5Solid/sort-alpha-down/14"
      }, {
        id: "owner",
        label: qx.locale.Manager.tr("Owner"),
        // icon: "@FontAwesome5Solid/sort-alpha-down/14"
      }, {
        id: "created",
        label: qx.locale.Manager.tr("Created"),
        // icon: "@FontAwesome5Solid/sort-alpha-down/14"
      }, {
        id: "modified",
        label: qx.locale.Manager.tr("Modified"),
        // icon: "@FontAwesome5Solid/sort-alpha-down/14"
      }];
    }
  },

  events: {
    "sortByChanged": "qx.event.type.Data"
  },

  properties: {
    field: {
      check: "String",
      init: null,
      event: "changeField",
      // apply: "_applySortField",
      nullable: false
    },
    direction: {
      check: "String",
      init: null,
      event: "changeDirection",
      // apply: "_applySortDirection",
      nullable: true
    },
  },

  members: {
    __buttonContainer: null,
    __resourceType: null,

    __buttonExecuted: function(btn) {
      this._applySortField(btn.btnId);
      this._applySortDirection(this.getDirection());
      // this.set({
      //   label: btn.getLabel(),
      //   icon: btn.getIcon()
      // });

      // const data = {
      //   "id": btn.btnId,
      // };
      // this.setSortedBy(data.id);
      // this._setSortField(field)
    },
    __handleSort: function (field, direction) {
      debugger
      this.fireDataEvent("sortByChanged", {
        field,
        direction
      });
    },
    _applySortDirection: function(value) {
      let direction;
      if (value === "desc") {
        direction = "asc"
      } else if (value === "asc") {
        direction = null
      } else {
        direction = "desc"
      }
      this.setDirection(direction);
    },

    _applySortField: function(optionId) {
      // let sort;
      let field;
      switch (optionId) {
        case "name":
          field = "name";
          break;
        case "owner":
          field = "prj_owner";
          break;
        case "created":
          field = "creation_date";
          break;
        case "modified":
          field = "last_change_date";
          break;
        default:
          field = "last_change_date";
      }
      return field;
      // this._setSortField(field)
      // this.fireDataEvent("sortByChanged", {
      //   field,
      // });
    },
  }
});
