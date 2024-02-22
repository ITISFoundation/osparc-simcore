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

qx.Class.define("osparc.dashboard.SortedByMenuButton", {
  extend: qx.ui.form.MenuButton,

  construct: function(resource = "study") {
    this.base(arguments, this.tr("Sort by"), "@FontAwesome5Solid/chevron-down/10");

    osparc.utils.Utils.setIdToWidget(this, "sortedByButton");

    const sortedByMenu = new qx.ui.menu.Menu().set({
      font: "text-14"
    });
    this.setMenu(sortedByMenu);

    this.__resourceType = resource;
    const options = this.self().getSortByOptions(resource);
    options.forEach((option, idx) => {
      const btn = new qx.ui.menu.Button(option.label);
      btn.btnId = option.id;
      btn.btnLabel = option.label;
      sortedByMenu.add(btn);

      btn.addListener("execute", () => this.__buttonExecuted(btn));

      if (idx === 0) {
        btn.execute();
      }
    });
  },

  statics: {
    getSortByOptions: function() {
      return [{
        id: "name-asc",
        label: qx.locale.Manager.tr("Name (ASC)")
      }, {
        id: "name-desc",
        label: qx.locale.Manager.tr("Name (DESC)")
      }, {
        id: "owner-asc",
        label: qx.locale.Manager.tr("Owner (ASC)")
      }, {
        id: "owner-desc",
        label: qx.locale.Manager.tr("Owner (DESC)")
      }, {
        id: "created-desc",
        label: qx.locale.Manager.tr("Created date (DESC)")
      }, {
        id: "created-asc",
        label: qx.locale.Manager.tr("Created date (ASC)")
      }, {
        id: "modified-desc",
        label: qx.locale.Manager.tr("Modified date (DESC)")
      }, {
        id: "modified-asc",
        label: qx.locale.Manager.tr("Modiefied date (ASC)")
      }];
    }
  },

  events: {
    "sortByChanged": "qx.event.type.Data"
  },

  members: {
    __resourceType: null,

    __buttonExecuted: function(btn) {
      this.set({
        label: btn.getLabel()
      });

      const data = {
        "id": btn.btnId,
      };
      console.debug(data.id)
      this.setSortedBy(data.id)
    },

    setSortedBy: function(optionId) {
      let sort;
      switch (optionId) {
        case "name-asc":
          sort = {
            field: "name",
            direction: "asc"
          };
          break;
        case "name-desc":
          sort = {
            field: "name",
            direction: "desc"
          };
          break;
        case "owner-asc":
          sort = {
            field: "prj_owner",
            direction: "asc"
          };
          break;
        case "owner-desc":
          sort = {
            field: "prj_owner",
            direction: "desc"
          };
          break;
        case "created-asc":
          sort = {
            field: "creation_date",
            direction: "asc"
          };
          break;
        case "created-desc":
          sort = {
            field: "creation_date",
            direction: "desc"
          };
          break;
        case "modified-asc":
          sort = {
            field: "last_change_date",
            direction: "asc"
          };
          break;
        default:
          sort = {
            field: "last_change_date",
            direction: "desc"
          }
      }
      this.fireDataEvent("sortByChanged", sort);
    },
  }
});
