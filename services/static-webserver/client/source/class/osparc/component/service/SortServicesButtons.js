/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (ignapas)

************************************************************************ */

qx.Class.define("osparc.component.service.SortServicesButtons", {
  extend: qx.ui.form.MenuButton,

  construct: function() {
    this.base(arguments, this.tr("Sort"), "@FontAwesome5Solid/chevron-down/10");

    this.set({
      marginRight: 8
    });

    const sortByMenu = new qx.ui.menu.Menu().set({
      font: "text-14"
    });
    this.setMenu(sortByMenu);

    const hitsDesc = new qx.ui.menu.RadioButton(this.tr("Hits Desc"));
    hitsDesc["sortBy"] = "hits";
    hitsDesc["orderBy"] = "down";
    const hitsAsc = new qx.ui.menu.RadioButton(this.tr("Hits Asc"));
    hitsAsc["sortBy"] = "hits";
    hitsAsc["orderBy"] = "up";
    const nameAsc = new qx.ui.menu.RadioButton(this.tr("Name Asc"));
    nameAsc["sortBy"] = "name";
    nameAsc["orderBy"] = "down";
    const nameDesc = new qx.ui.menu.RadioButton(this.tr("Name Desc"));
    nameDesc["sortBy"] = "name";
    nameDesc["orderBy"] = "up";
    hitsDesc.addListener("execute", () => this.__btnExecuted(hitsDesc));
    hitsAsc.addListener("execute", () => this.__btnExecuted(hitsAsc));
    nameAsc.addListener("execute", () => this.__btnExecuted(nameAsc));
    nameDesc.addListener("execute", () => this.__btnExecuted(nameDesc));

    const sortByGroup = new qx.ui.form.RadioGroup();
    [
      hitsDesc,
      hitsAsc,
      nameAsc,
      nameDesc
    ].forEach(btn => {
      sortByMenu.add(btn);
      sortByGroup.add(btn);
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
    __btnExecuted: function(btn) {
      const data = {
        "sort": btn["sortBy"],
        "order": btn["orderBy"]
      };
      this.fireDataEvent("sortBy", data);
    }
  }
});
