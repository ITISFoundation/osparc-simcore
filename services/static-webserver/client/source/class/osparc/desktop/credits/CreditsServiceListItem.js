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

qx.Class.define("osparc.desktop.credits.CreditsServiceListItem", {
  extend: osparc.ui.list.ListItem,

  construct: function(serviceKey, credits, percentage) {
    this.base(arguments);

    const layout = this._getLayout();
    layout.setSpacingX(10);
    layout.setSpacingY(5);
    layout.setColumnFlex(this.self().GRID.ICON.column, 0);
    layout.setColumnFlex(this.self().GRID.NAME.column, 1);
    layout.setColumnFlex(this.self().GRID.CREDITS.column, 0);

    const icon = this.getChildControl("icon");
    const name = this.getChildControl("title");
    const serviceMetadata = osparc.service.Utils.getLatest(serviceKey);
    if (serviceMetadata) {
      icon.setSource(serviceMetadata["thumbnail"]);
      name.setValue(serviceMetadata["name"]);
    } else {
      const serviceName = serviceKey.split("/").pop()
      name.setValue(serviceName);
    }
    this.getChildControl("percentage").setValue(percentage);
    this.getChildControl("credits").setValue(credits + " used");
  },

  statics: {
    GRID: {
      ICON: {
        column: 0,
        row: 0,
        rowSpan: 2
      },
      NAME: {
        column: 1,
        row: 0,
        rowSpan: 1
      },
      PERCENTAGE: {
        column: 1,
        row: 1,
        rowSpan: 1
      },
      CREDITS: {
        column: 2,
        row: 0,
        rowSpan: 2
      }
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon": {
          control = new osparc.ui.basic.Thumbnail(null, 30, 30).set({
            minHeight: 30,
            minWidth: 30
          });
          control.getChildControl("image").set({
            anonymous: true
          });
          this._add(control, this.self().GRID.ICON);
          break;
        }
        case "title":
          control = new qx.ui.basic.Label().set({
            font: "text-12",
            alignY: "middle",
            maxWidth: 200,
            allowGrowX: true,
            rich: true,
          });
          this._add(control, this.self().GRID.NAME);
          break;
        case "percentage":
          control = new qx.ui.indicator.ProgressBar().set({
            height: 10
          });
          this._add(control, this.self().GRID.PERCENTAGE);
          break;
        case "credits":
          control = new qx.ui.basic.Label().set({
            font: "text-14",
            alignY: "middle"
          });
          this._add(control, this.self().GRID.CREDITS);
          break;
      }

      return control || this.base(arguments, id);
    }
  }
});
