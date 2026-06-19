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
    this.base(arguments, this.tr("Sort"), "@FontAwesomeSolid/chevron-down/10");

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
      const btn = new qx.ui.menu.Button(option.label);
      btn.field = option.id;
      // Sort by last modified date
      if (idx === options.length -1) {
        this.__selectedMenuButton = btn;
        btn.setIcon("@FontAwesomeSolid/arrow-down/14");
      }
      sortedByMenu.add(btn);

      btn.addListener("execute", () => this.__buttonExecuted(btn));
    });
  },

  statics: {
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
    sort: {
      check: "Object",
      init: {
        field: "last_change_date",
        direction: true
      },
      nullable: false,
      event: "changeSort",
      apply: "__handleSortEvent",
    }
  },

  members: {
    __selectedMenuButton: null,

    __buttonExecuted: function(btn) {
      if (this.__selectedMenuButton) {
        this.__selectedMenuButton.setIcon(null);
      }
      this.__selectedMenuButton = btn;
      this.set({
        label: btn.getLabel(),
        icon: "@FontAwesomeSolid/chevron-down/10"
      });

      const field = btn.field;
      if (field === this.getSort().field) {
        const { direction } = this.getSort();
        this.setSort({
          field,
          direction: !direction
        });
      } else {
        this.setSort({
          field,
          direction: true
        });
      }
    },

    __handleSortEvent: function({field, direction}) {
      this.__selectedMenuButton.setIcon(direction ? "@FontAwesomeSolid/arrow-down/14" : "@FontAwesomeSolid/arrow-up/14")
      this.setIcon(direction ? "@FontAwesomeSolid/arrow-down/14" : "@FontAwesomeSolid/arrow-up/14")
      const sort = {
        field: field,
        direction: direction ? "desc" : "asc"
      };
      this.fireDataEvent("sortByChanged", sort);
    },

    hideOptionButton: function(field) {
      const btn = this.getMenu().getChildren().find(btn => btn.field === field);
      if (btn) {
        btn.exclude();
      }
    },

    showAllOptions: function() {
      this.getMenu().getChildren().forEach(btn => btn.show());
    },
  }
});
