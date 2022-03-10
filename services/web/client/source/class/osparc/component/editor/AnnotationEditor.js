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

qx.Class.define("osparc.component.editor.AnnotationEditor", {
  extend: qx.ui.core.Widget,

  construct: function(annotation) {
    this.base(arguments);

    const layout = new qx.ui.layout.Grid(5, 5);
    layout.setRowFlex(1, 1);
    layout.setColumnFlex(0, 1);
    this._setLayout(layout);

    this.__annotation = annotation;

    this.__populateForm();
  },

  members: {
    __annotation: null,

    __populateForm: function() {
      this._add(new qx.ui.basic.Label(this.tr("Color")), {
        row: 0,
        column: 0
      });

      const colorPicker = this.__colorPicker = new osparc.component.form.ColorPicker();
      this.__annotation.bind("color", colorPicker, "color");
      this._add(colorPicker, {
        row: 0,
        column: 1
      });
    }
  }
});
