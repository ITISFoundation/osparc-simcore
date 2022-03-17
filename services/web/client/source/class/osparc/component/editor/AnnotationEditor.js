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

    this.set({
      padding: 10
    });

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
      this._removeAll();

      let row = 0;
      this._add(new qx.ui.basic.Label(this.tr("Color")), {
        row,
        column: 0
      });
      const colorPicker = new osparc.component.form.ColorPicker();
      annotation.bind("color", colorPicker, "color");
      colorPicker.bind("color", annotation, "color");
      this._add(colorPicker, {
        row,
        column: 1
      });
      row++;

      if (annotation.getType() === "text") {
        this._add(new qx.ui.basic.Label(this.tr("Text")), {
          row,
          column: 0
        });
        const textField = new qx.ui.form.TextField(annotation.getAttributes().text);
        textField.addListener("changeValue", e => annotation.setText(e.getData()));
        this._add(textField, {
          row,
          column: 1
        });
      }
    }
  }
});
