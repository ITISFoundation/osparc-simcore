/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.widget.SectionBox", {
  extend: qx.ui.core.Widget,
  include: [qx.ui.core.MRemoteChildrenHandling, qx.ui.core.MLayoutHandling],

  /**
   * @param legend {String?} Section title
   * @param icon {String?} Section icon
   */
  construct: function(legend, icon) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());

    // ensure child controls exist
    this.getChildControl("frame");
    this.getChildControl("legend");

    if (legend) {
      this.setLegend(legend);
    }
    if (icon) {
      this.setIcon(icon);
    }
  },

  properties: {
    legend: {
      check: "String",
      init: "",
      event: "changeLegend",
    },

    icon: {
      check: "String",
      init: "",
      event: "changeIcon",
    },

    legendBackgroundColor: {
      check: "Color",
      init: "background-main-1",
      event: "changeLegendBackgroundColor",
    },
  },

  members: {
    _frame: null,

    // Children you add to this widget will be forwarded into the frame:
    getChildrenContainer: function() {
      return this._frame || this.getChildControl("frame");
    },

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "frame":
          control = this._frame = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
            decorator: new qx.ui.decoration.Decorator().set({
              width: 1,
              style: "solid",
              color: "background-main-2",
              radius: 4,
            }),
            padding: [10 + 6, 10, 10, 10],
            backgroundColor: "transparent",
          });
          // full size, but pushed down by frameTop
          this._add(control, { left: 0, right: 0, bottom: 0, top: 10 });
          break;
        case "legend":
          control = new qx.ui.basic.Atom().set({
            font: "text-14",
            padding: [0, 6],
          });
          this.bind("legend", control, "label");
          this.bind("icon", control, "icon");
          this.bind("legendBackgroundColor", control, "backgroundColor");
          this._add(control, { left: 16, top: 0 });
          break;
      }
      return control || this.base(arguments, id);
    },

    addHelper: function(message, font) {
      font = font || "text-13";
      const label = new qx.ui.basic.Label(message).set({
        font,
      });
      this.add(label);
      return label;
    },
  }
});
