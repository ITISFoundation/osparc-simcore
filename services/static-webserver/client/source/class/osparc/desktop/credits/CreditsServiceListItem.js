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

  construct: function(serviceKey, credits, hours, percentage) {
    this.base(arguments);

    const layout = this._getLayout();
    layout.setSpacingX(12);
    layout.setSpacingY(4);
    layout.setColumnFlex(this.self().GRID.ICON.column, 0);
    layout.setColumnFlex(this.self().GRID.NAME.column, 1);
    layout.setColumnFlex(this.self().GRID.TIME.column, 0);
    layout.setColumnFlex(this.self().GRID.CREDITS.column, 0);

    const icon = this.getChildControl("icon");
    const name = this.getChildControl("title");
    const serviceMetadata = osparc.service.Utils.getLatest(serviceKey);
    if (serviceMetadata) {
      const source = osparc.utils.Utils.getIconFromResource(serviceMetadata);
      icon.setSource(source);
      name.setValue(serviceMetadata["name"]);
    } else {
      icon.setSource(osparc.dashboard.CardBase.PRODUCT_THUMBNAIL);
      const serviceName = serviceKey.split("/").pop();
      name.setValue(serviceName);
    }
    this.getChildControl("percentage").set({
      maximum: 100,
      value: percentage
    });
    this.getChildControl("time").setValue(hours + " h");
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
        row: 0
      },
      PERCENTAGE: {
        column: 1,
        row: 1
      },
      TIME: {
        column: 2,
        row: 0,
        rowSpan: 2
      },
      CREDITS: {
        column: 3,
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
          control = new osparc.ui.basic.Thumbnail(null, 32, 32).set({
            minHeight: 32,
            minWidth: 32
          });
          control.getChildControl("image").set({
            decorator: "rounded",
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
            backgroundColor: "transparent",
            maxHeight: 8,
            margin: 0,
            padding: 0
          });
          control.getChildControl("progress").set({
            backgroundColor: "strong-main"
          });
          control.getContentElement().setStyles({
            "border-radius": "2px"
          });
          this._add(control, this.self().GRID.PERCENTAGE);
          break;
        case "time":
          control = new qx.ui.basic.Label().set({
            font: "text-14",
            alignY: "middle"
          });
          this._add(control, this.self().GRID.TIME);
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
