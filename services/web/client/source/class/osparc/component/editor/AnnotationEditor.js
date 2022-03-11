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
    layout.setColumnAlign(0, "right", "middle");
    layout.setColumnAlign(1, "left", "middle");
    this._setLayout(layout);

    if (annotation) {
      this.setAnnotation(annotation);
    }
  },

  properties: {
    annotation: {
      check: "osparc.component.workbench.Annotation",
      apply: "__applyAnnotation"
    }
  },

  members: {
    __applyAnnotation: function(annotation) {
      this._add(new qx.ui.basic.Label(this.tr("Color")), {
        row: 0,
        column: 0
      });

      const colorPicker = this.__colorPicker = new osparc.component.form.ColorPicker();
      annotation.bind("color", colorPicker, "color");
      colorPicker.bind("color", annotation, "color");
      this._add(colorPicker, {
        row: 0,
        column: 1
      });
    }
  }
});
