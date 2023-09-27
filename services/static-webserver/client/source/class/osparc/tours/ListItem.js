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

qx.Class.define("osparc.tours.ListItem", {
  extend: qx.ui.core.Widget,

  construct: function(tour) {
    this.base(arguments);

    const layout = new qx.ui.layout.Grid(5, 5);
    layout.setColumnFlex(0, 1);

    this._setLayout(layout);

    this.set({
      backgroundColor: "material-button-background",
      cursor: "pointer",
      allowGrowX: true,
      padding: 10
    });

    const titleLabel = new qx.ui.basic.Label(tour.name).set({
      font: "text-14",
      rich: true
    });
    this._add(titleLabel, {
      row: 0,
      column: 0
    });
    if (tour.description) {
      const descriptionLabel = new qx.ui.basic.Label(tour.description).set({
        font: "text-13",
        rich: true
      });
      this._add(descriptionLabel, {
        row: 1,
        column: 0
      });
    }
    const image = new qx.ui.basic.Image("@FontAwesome5Solid/arrow-right/14").set({
      alignY: "middle"
    });
    this._add(image, {
      row: 0,
      column: 1,
      rowSpan: 2
    });

    this.addListener("pointerover", () => this.setBackgroundColor("material-button-background-hovered"), this);
    this.addListener("pointerout", () => this.setBackgroundColor("material-button-background"), this);
  }
});
