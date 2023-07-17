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
      init: null,
      nullable: true,
      apply: "__applyAnnotation"
    },

    marker: {
      check: "Object",
      init: null,
      nullable: true,
      apply: "__applyMarker"
    }
  },

  members: {
    __addColor: function() {
      this._add(new qx.ui.basic.Label(this.tr("Color")), {
        row: 0,
        column: 0
      });
      const colorPicker = new osparc.component.form.ColorPicker();
      this._add(colorPicker, {
        row: 0,
        column: 1
      });
      return colorPicker;
    },

    __applyAnnotation: function(annotation) {
      this._removeAll();

      if (annotation === null) {
        return;
      }

      let row = 0;
      if (["text", "rect"].includes(annotation.getType())) {
        const colorPicker = this.__addColor();
        annotation.bind("color", colorPicker, "color");
        colorPicker.bind("color", annotation, "color");
        row++;
      }

      const attrs = annotation.getAttributes();
      if (annotation.getType() === "text") {
        this._add(new qx.ui.basic.Label(this.tr("Text")), {
          row,
          column: 0
        });
        const textField = new qx.ui.form.TextField(attrs.text);
        textField.addListener("changeValue", e => annotation.setText(e.getData()));
        this._add(textField, {
          row,
          column: 1
        });
        row++;
      } else if (annotation.getType() === "note") {
        this._add(new qx.ui.basic.Label(this.tr("Note")), {
          row,
          column: 0
        });
        const textArea = new qx.ui.form.TextArea(attrs.text).set({
          autoSize: true,
          minHeight: 70,
          maxHeight: 140
        });
        textArea.addListener("changeValue", e => annotation.setText(e.getData()));
        this._add(textArea, {
          row,
          column: 1
        });
        row++;
      }

      if (annotation.getType() === "text") {
        this._add(new qx.ui.basic.Label(this.tr("Size")), {
          row,
          column: 0
        });
        const fontSizeField = new qx.ui.form.Spinner(attrs.fontSize);
        fontSizeField.addListener("changeValue", e => annotation.setFontSize(e.getData()));
        this._add(fontSizeField, {
          row,
          column: 1
        });
        row++;
      }

      this.__makeItModal();
    },

    __applyMarker: function(marker) {
      this._removeAll();

      if (marker === null) {
        return;
      }

      const colorPicker = this.__addColor();
      marker.bind("color", colorPicker, "color");
      colorPicker.bind("color", marker, "color");

      this.__makeItModal();
    },

    __makeItModal: function() {
      this.show();

      const showHint = () => this.show();
      const hideHint = () => this.exclude();
      const tapListener = event => {
        if (osparc.utils.Utils.isMouseOnElement(this, event)) {
          return;
        }
        hideHint();
        this.set({
          annotation: null,
          marker: null
        });
        document.removeEventListener("mousedown", tapListener);
      };
      showHint();
      document.addEventListener("mousedown", tapListener);
    }
  }
});
