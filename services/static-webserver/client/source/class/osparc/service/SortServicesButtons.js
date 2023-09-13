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

qx.Class.define("osparc.service.SortServicesButtons", {
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

    const hitsDesc = new qx.ui.menu.Button().set({
      label: this.tr("Hits"),
      icon: "@FontAwesome5Solid/sort-numeric-down/14"
    });
    hitsDesc["sortBy"] = "hits";
    hitsDesc["orderBy"] = "down";
    const nameAsc = new qx.ui.menu.Button().set({
      label: this.tr("Name Asc"),
      icon: "@FontAwesome5Solid/sort-alpha-down/14"
    });
    nameAsc["sortBy"] = "name";
    nameAsc["orderBy"] = "down";
    const nameDesc = new qx.ui.menu.Button().set({
      label: this.tr("Name Desc"),
      icon: "@FontAwesome5Solid/sort-alpha-up/14"
    });
    nameDesc["sortBy"] = "name";
    nameDesc["orderBy"] = "up";

    [
      hitsDesc,
      nameAsc,
      nameDesc
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
      "sort": "hits",
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
