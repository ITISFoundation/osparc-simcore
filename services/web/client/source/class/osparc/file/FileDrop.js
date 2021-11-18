/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.file.FileDrop", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());
    this.set({
      droppable: true
    });

    this.getContentElement().setStyles(this.self().getBorderStyle());

    this._createChildControlImpl("drop-here");
    this._createChildControlImpl("svg-layer");
  },

  statics: {
    getBorderStyle: function() {
      return {
        "border-radius": "20px",
        "border-color": qx.theme.manager.Color.getInstance().resolve("contrasted-background+"),
        // "border-color": qx.theme.manager.Color.getInstance().resolve("blue"),
        "border-style": "dotted"
      };
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control = null;
      switch (id) {
        case "drop-here":
          control = new qx.ui.basic.Label(this.tr("Drop here")).set({
            font: "title-14",
            alignX: "center",
            alignY: "middle"
          });
          this._add(control, {
            top: 0,
            right: 0,
            bottom: 0,
            left: 0
          });
          break;
        case "svg-layer":
          control = new osparc.component.workbench.SvgWidget();
          this._add(control, {
            top: 0,
            right: 0,
            bottom: 0,
            left: 0
          });
          break;
        case "drop-me":
          control = new qx.ui.basic.Label(this.tr("Drop me")).set({
            font: "title-14"
          });
          this._add(control);
          break;
      }
    }
  }
});
