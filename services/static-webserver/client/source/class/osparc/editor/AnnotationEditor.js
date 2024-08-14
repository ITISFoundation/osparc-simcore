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

qx.Class.define("osparc.editor.AnnotationEditor", {
  extend: qx.ui.form.renderer.Single,

  construct: function(annotation) {
    const form = this.__form = new qx.ui.form.Form();
    this.base(arguments, form);

    if (annotation) {
      this.setAnnotation(annotation);
    }
  },

  properties: {
    annotation: {
      check: "osparc.workbench.Annotation",
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
    __form: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "text-field":
          control = new qx.ui.form.TextField();
          this.__form.add(control, "Text", null, "text");
          break;
        case "text-area":
          control = new qx.ui.form.TextArea().set({
            autoSize: true,
            minHeight: 70,
            maxHeight: 140
          });
          this.__form.add(control, "Note", null, "note");
          break;
        case "color-picker":
          control = new osparc.form.ColorPicker();
          this.__form.add(control, "Color", null, "color");
          break;
        case "size":
          control = new qx.ui.form.Spinner();
          this.__form.add(control, "Size", null, "size");
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyAnnotation: function(annotation) {
      this._removeAll();
      if (annotation === null) {
        return;
      }

      const attrs = annotation.getAttributes();
      if (annotation.getType() === "text") {
        const textField = this.getChildControl("text-field").set({
          value: attrs.text
        });
        textField.addListener("changeValue", e => annotation.setText(e.getData()));
      } else if (annotation.getType() === "note") {
        const textArea = this.getChildControl("text-area").set({
          value: attrs.text
        });
        textArea.addListener("changeValue", e => annotation.setText(e.getData()));
      }

      if (["text", "rect"].includes(annotation.getType())) {
        const colorPicker = this.getChildControl("color-picker");
        annotation.bind("color", colorPicker, "value");
        colorPicker.bind("value", annotation, "color");
      }

      if (annotation.getType() === "text") {
        const fontSizeField = this.getChildControl("size").set({
          value: attrs.fontSize
        })
        fontSizeField.addListener("changeValue", e => annotation.setFontSize(e.getData()));
      }
    },

    __applyMarker: function(marker) {
      this._removeAll();
      if (marker === null) {
        return;
      }

      const colorPicker = this.getChildControl("color-picker");
      marker.bind("color", colorPicker, "color");
      colorPicker.bind("color", marker, "color");
    },

    makeItModal: function() {
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
