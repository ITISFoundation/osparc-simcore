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

qx.Class.define("osparc.vipMarket.SortModelsButtons", {
  extend: qx.ui.form.MenuButton,

  construct: function() {
    this.base(arguments, this.tr("Sort"), "@FontAwesome5Solid/chevron-down/10");

    this.set({
      iconPosition: "left",
      marginRight: 8
    });

    const sortByMenu = new qx.ui.menu.Menu().set({
      font: "text-14"
    });
    this.setMenu(sortByMenu);

    const nameAsc = new qx.ui.menu.Button().set({
      label: this.tr("Name"),
      icon: "@FontAwesome5Solid/sort-alpha-down/14"
    });
    nameAsc["sortBy"] = "name";
    nameAsc["orderBy"] = "down";
    const nameDesc = new qx.ui.menu.Button().set({
      label: this.tr("Name"),
      icon: "@FontAwesome5Solid/sort-alpha-up/14"
    });
    nameDesc["sortBy"] = "name";
    nameDesc["orderBy"] = "up";

    const dateDesc = new qx.ui.menu.Button().set({
      label: this.tr("Date"),
      icon: "@FontAwesome5Solid/arrow-down/14"
    });
    dateDesc["sortBy"] = "date";
    dateDesc["orderBy"] = "down";
    const dateAsc = new qx.ui.menu.Button().set({
      label: this.tr("Date"),
      icon: "@FontAwesome5Solid/arrow-up/14"
    });
    dateAsc["sortBy"] = "date";
    dateAsc["orderBy"] = "down";

    [
      nameAsc,
      nameDesc,
      dateDesc,
      dateAsc,
    ].forEach((btn, idx) => {
      sortByMenu.add(btn);

      btn.addListener("execute", () => this.__buttonExecuted(btn));

      if (idx === 0) {
        btn.execute();
      }
    });
  },

  events: {
    "sortBy": "qx.event.type.Data"
  },

  statics: {
    DefaultSorting: {
      "sort": "name",
      "order": "down"
    }
  },

  members: {
    __buttonExecuted: function(btn) {
      this.set({
        label: btn.getLabel(),
        icon: btn.getIcon()
      });

      const data = {
        "sort": btn["sortBy"],
        "order": btn["orderBy"]
      };
      this.fireDataEvent("sortBy", data);
    }
  }
});
